"""
Unit tests for the SQS poller service.
"""

import asyncio
from unittest.mock import MagicMock, patch
import pytest

from db.models import Telemetry
from services.sqs_poller import poll_loop


@pytest.mark.asyncio
async def test_sqs_poller_success(db_session):
    """
    Test that a valid SQS telemetry message is successfully parsed,
    written to the database, and deleted from the queue.
    """
    mock_sqs = MagicMock()
    # Mock receive_message returning a single valid Phase 2 message
    mock_sqs.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "msg_001",
                "ReceiptHandle": "receipt_001",
                "Attributes": {"MessageGroupId": "EV_B0005_001"},
                "Body": (
                    '{"schema_version": "2.0", '
                    '"source": "ev_simulator_aws", '
                    '"battery_id": "EV_B0005_001", '
                    '"vehicle_id": "VH_TESLA_042", '
                    '"timestamp": "2024-01-15T14:23:45.123Z", '
                    '"sequence_id": "EV_B0005_001_000147", '
                    '"cycle_number": 147, '
                    '"cycle_type": "discharge", '
                    '"measurements": {'
                    '  "voltage_v": 3.8124, '
                    '  "current_a": -1.9987, '
                    '  "temperature_c": 24.5, '
                    '  "capacity_mah": 1823.4'
                    '}}'
                ),
            }
        ]
    }

    stop_event = asyncio.Event()

    # Set the stop event when delete_message is called to stop the polling loop
    def stop_loop(*args, **kwargs):
        stop_event.set()
        return {}

    mock_sqs.delete_message.side_effect = stop_loop

    with patch("services.sqs_poller.get_sqs_client", return_value=mock_sqs), patch(
        "services.sqs_poller.SessionLocal", return_value=db_session
    ):
        await poll_loop("http://dummy-queue", "http://dummy-dlq", stop_event)

    # Assertions
    mock_sqs.receive_message.assert_called()
    mock_sqs.delete_message.assert_called_with(
        QueueUrl="http://dummy-queue", ReceiptHandle="receipt_001"
    )

    # Verify database entry
    telemetry_record = (
        db_session.query(Telemetry).filter_by(battery_id="EV_B0005_001").first()
    )
    assert telemetry_record is not None
    assert float(telemetry_record.voltage_v) == 3.8124
    assert telemetry_record.cycle_number == 147


@pytest.mark.asyncio
async def test_sqs_poller_dlq_routing(db_session):
    """
    Test that a malformed message is retried up to 3 times, then routed
    to the DLQ and deleted from the main queue.
    """
    mock_sqs = MagicMock()
    # Mock receive_message yielding the same malformed message every iteration
    mock_sqs.receive_message.return_value = {
        "Messages": [
            {
                "MessageId": "msg_bad_001",
                "ReceiptHandle": "receipt_bad_001",
                "Attributes": {"MessageGroupId": "bad_messages"},
                "Body": '{"schema_version": "2.0", "source": "invalid_payload"}',  # invalid schema
            }
        ]
    }

    stop_event = asyncio.Event()

    # Stop the loop when delete_message is called (which happens after DLQ routing)
    def stop_on_delete(*args, **kwargs):
        stop_event.set()
        return {}

    mock_sqs.delete_message.side_effect = stop_on_delete

    with patch("services.sqs_poller.get_sqs_client", return_value=mock_sqs), patch(
        "services.sqs_poller.SessionLocal", return_value=db_session
    ):
        await poll_loop("http://dummy-queue", "http://dummy-dlq", stop_event)

    # Assert send_message to DLQ was called
    mock_sqs.send_message.assert_called_once()
    _, kwargs = mock_sqs.send_message.call_args
    assert kwargs["QueueUrl"] == "http://dummy-dlq"
    assert kwargs["MessageDeduplicationId"] == "msg_bad_001"
    assert "Error" in kwargs["MessageAttributes"]

    # Assert message was deleted from the main queue
    mock_sqs.delete_message.assert_called_with(
        QueueUrl="http://dummy-queue", ReceiptHandle="receipt_bad_001"
    )
