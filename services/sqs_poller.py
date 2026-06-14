"""
SQS poller service to listen for Phase 2 battery telemetry messages
and ingest them directly.
"""

import asyncio
import json
import logging
import os
import time
import boto3
from sqlalchemy.orm import Session

from db.session import SessionLocal
from models.schemas import IngestPayloadV2
from services.ingest_service import ingest_telemetry_shared

logger = logging.getLogger("sqs_poller")

# Maximum entries tracked in the retry_counts dict before oldest are evicted.
# Prevents unbounded memory growth if many unique messages fail over time.
MAX_RETRY_ENTRIES = 10_000

# Entries older than this (seconds) are purged on each cleanup pass.
RETRY_ENTRY_TTL_SECONDS = 3600  # 1 hour

# Backoff delay (seconds) after failing to route a message to the DLQ,
# preventing a tight loop when the DLQ is persistently unreachable.
DLQ_FAILURE_BACKOFF_SECONDS = 5.0


def get_sqs_client():
    """Build boto3 SQS client using env overrides for local emulation."""
    endpoint_url = os.getenv("SQS_ENDPOINT_URL")
    region_name = os.getenv("AWS_REGION", "us-east-1")
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

    kwargs = {
        "region_name": region_name,
    }
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    if access_key:
        kwargs["aws_access_key_id"] = access_key
    if secret_key:
        kwargs["aws_secret_access_key"] = secret_key

    return boto3.client("sqs", **kwargs)


def init_queues() -> None:
    """
    Programmatic queue initialization for local development.
    Creates DLQ and Main FIFO queues and binds them via RedrivePolicy.
    """
    if os.getenv("CREATE_QUEUES_ON_STARTUP", "false").lower() != "true":
        return

    sqs = get_sqs_client()
    try:
        # 1. Create DLQ
        dlq_res = sqs.create_queue(
            QueueName="ev-telemetry-dlq.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
            },
        )
        dlq_url = dlq_res["QueueUrl"]

        # 2. Get DLQ ARN
        attrs = sqs.get_queue_attributes(QueueUrl=dlq_url, AttributeNames=["QueueArn"])
        dlq_arn = attrs["Attributes"]["QueueArn"]

        # 3. Create main queue linked to DLQ
        sqs.create_queue(
            QueueName="ev-telemetry.fifo",
            Attributes={
                "FifoQueue": "true",
                "ContentBasedDeduplication": "true",
                "RedrivePolicy": json.dumps(
                    {"deadLetterTargetArn": dlq_arn, "maxReceiveCount": "3"}
                ),
            },
        )
        logger.info("SQS FIFO queues initialized successfully.")
    except Exception as e:
        logger.warning(f"Error during SQS queue initialization: {e}")


def _cleanup_stale_retry_entries(
    retry_counts: dict[str, dict], now: float
) -> None:
    """
    Evict retry_counts entries whose timestamp exceeds the TTL.
    Also enforces the hard cap by removing the oldest entries if over limit.
    """
    # 1. TTL-based eviction
    stale_keys = [
        k
        for k, v in retry_counts.items()
        if (now - v["ts"]) > RETRY_ENTRY_TTL_SECONDS
    ]
    for k in stale_keys:
        del retry_counts[k]

    # 2. Hard cap eviction (oldest first)
    if len(retry_counts) > MAX_RETRY_ENTRIES:
        sorted_keys = sorted(retry_counts, key=lambda k: retry_counts[k]["ts"])
        excess = len(retry_counts) - MAX_RETRY_ENTRIES
        for k in sorted_keys[:excess]:
            del retry_counts[k]


async def poll_loop(queue_url: str, dlq_url: str, stop_event: asyncio.Event) -> None:
    """
    Receive, validate, and process SQS messages.
    Ensures graceful shutdown, and handles retries for schema/parsing errors.
    """
    sqs = get_sqs_client()
    # retry_counts stores {MessageId: {"count": int, "ts": float}}
    retry_counts: dict[str, dict] = {}
    last_cleanup = time.monotonic()

    logger.info(f"Starting SQS poll loop for: {queue_url}")

    while not stop_event.is_set():
        try:
            # Periodic cleanup (every 5 minutes)
            now = time.monotonic()
            if now - last_cleanup > 300:
                _cleanup_stale_retry_entries(retry_counts, now)
                last_cleanup = now

            # Poll messages in a thread pool (blocking call, up to 20s)
            response = await asyncio.to_thread(
                sqs.receive_message,
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=20,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])
            if not messages:
                continue

            for msg in messages:
                if stop_event.is_set():
                    break

                msg_id = msg.get("MessageId")
                receipt_handle = msg.get("ReceiptHandle")
                body_str = msg.get("Body", "")

                try:
                    # 1. Parse JSON body
                    try:
                        body_dict = json.loads(body_str)
                    except json.JSONDecodeError as dec_err:
                        raise ValueError(f"JSON decode failed: {dec_err}")

                    # 2. Validate against Phase 2 schema
                    payload = IngestPayloadV2(**body_dict)

                    # 3. Direct database writes (using dedicated background session)
                    db: Session = SessionLocal()
                    try:
                        ingest_telemetry_shared(payload, db, source="poller")
                    finally:
                        db.close()

                    # 4. Complete -> Delete from queue
                    await asyncio.to_thread(
                        sqs.delete_message,
                        QueueUrl=queue_url,
                        ReceiptHandle=receipt_handle,
                    )

                    # Clean up retry counters on success
                    retry_counts.pop(msg_id, None)

                except Exception as e:
                    logger.error(f"Error processing SQS message {msg_id}: {e}")

                    # Increment failure count with timestamp
                    entry = retry_counts.get(msg_id, {"count": 0, "ts": time.monotonic()})
                    entry["count"] += 1
                    entry["ts"] = time.monotonic()
                    retry_counts[msg_id] = entry

                    if entry["count"] >= 3:
                        logger.warning(
                            f"Message {msg_id} failed {entry['count']} times. Sending to DLQ..."
                        )
                        # SQS FIFO requires Group ID and Deduplication ID
                        msg_attrs = msg.get("Attributes", {})
                        group_id = msg_attrs.get("MessageGroupId", "dlq_fallback")

                        try:
                            # Forward message to DLQ
                            await asyncio.to_thread(
                                sqs.send_message,
                                QueueUrl=dlq_url,
                                MessageBody=body_str,
                                MessageGroupId=group_id,
                                MessageDeduplicationId=msg_id,
                                MessageAttributes={
                                    "Error": {
                                        "DataType": "String",
                                        "StringValue": str(e),
                                    }
                                },
                            )
                            # Remove from main queue
                            await asyncio.to_thread(
                                sqs.delete_message,
                                QueueUrl=queue_url,
                                ReceiptHandle=receipt_handle,
                            )
                        except Exception as dlq_err:
                            logger.error(
                                f"Failed to route message {msg_id} to DLQ: {dlq_err}"
                            )
                            # Backoff to prevent tight loop when DLQ is unreachable
                            await asyncio.sleep(DLQ_FAILURE_BACKOFF_SECONDS)

                        # Always clean up the entry after DLQ attempt (success or failure)
                        # to prevent infinite re-routing loops on the next receive
                        retry_counts.pop(msg_id, None)

        except Exception as poll_err:
            logger.error(f"Error in SQS poll loop cycle: {poll_err}")
            await asyncio.sleep(2.0)  # Throttling error retry

    logger.info("SQS poll loop stopped cleanly.")
