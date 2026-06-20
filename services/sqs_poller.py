"""
SQS poller service to listen for Phase 2 battery telemetry messages
and ingest them directly.
"""

import asyncio
import json
import logging
import os
import boto3
from sqlalchemy.orm import Session

from db.session import SessionLocal
from models.schemas import IngestPayloadV2
from services.ingest_service import ingest_telemetry_shared

logger = logging.getLogger("sqs_poller")


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


async def poll_loop(queue_url: str, dlq_url: str, stop_event: asyncio.Event) -> None:
    """
    Receive, validate, and process SQS messages.
    Ensures graceful shutdown, and handles retries for schema/parsing errors.
    """
    sqs = get_sqs_client()
    retry_counts = {}  # MessageId -> retry_count

    logger.info(f"Starting SQS poll loop for: {queue_url}")

    while not stop_event.is_set():
        try:
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

                    # Clean up retry counters
                    if msg_id in retry_counts:
                        del retry_counts[msg_id]

                except Exception as e:
                    logger.error(f"Error processing SQS message {msg_id}: {e}")
                    # Increment failure count
                    retry_counts[msg_id] = retry_counts.get(msg_id, 0) + 1

                    if retry_counts[msg_id] >= 3:
                        logger.warning(
                            f"Message {msg_id} failed {retry_counts[msg_id]} times. Sending to DLQ..."
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

                        if msg_id in retry_counts:
                            del retry_counts[msg_id]

        except Exception as poll_err:
            logger.error(f"Error in SQS poll loop cycle: {poll_err}")
            await asyncio.sleep(2.0)  # Throttling error retry

    logger.info("SQS poll loop stopped cleanly.")
