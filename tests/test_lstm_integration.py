"""
Integration tests for LSTM prediction trigger during telemetry ingestion.
"""

import os
from unittest.mock import patch
import pytest

from db.models import RULPrediction


def test_lstm_inference_trigger_on_10th_message(client, db_session):
    """
    Ingest 9 messages and verify no LSTM triggers are run.
    Ingest the 10th message and verify that ml_service.predict_rul is called
    and a prediction record is inserted into the database.
    """
    with patch("services.ingest_service.predict_rul") as mock_predict, patch.dict(
        os.environ, {"INTERNAL_API_KEY": "test_secret_key"}
    ), patch("services.ingest_service.MIN_SEQUENCE_LENGTH", 10):
        mock_predict.return_value = {
            "predicted_rul_cycles": 213,
            "confidence_lower": 188,
            "confidence_upper": 238,
            "model_version": "v2.0",
        }

        headers = {"X-Internal-API-Key": "test_secret_key"}

        # 1. Send first 9 messages (no trigger expected)
        for i in range(1, 10):
            payload = {
                "schema_version": "1.0",
                "source": "ev_simulator_local",
                "battery_id": "LSTM_TEST_BATTERY",
                "vehicle_id": "VH_TESLA_001",
                "timestamp": f"2024-01-15T14:23:0{i}.000Z",
                "cycle_number": i,
                "cycle_type": "discharge",
                "measurements": {
                    "voltage_v": 3.8,
                    "current_a": -2.0,
                    "temperature_c": 25.0,
                    "capacity_mah": 1900.0 - i,
                },
            }
            response = client.post("/api/v1/ingest", json=payload, headers=headers)
            assert response.status_code == 202

        # Verify no database rows and no calls
        predictions = (
            db_session.query(RULPrediction)
            .filter_by(battery_id="LSTM_TEST_BATTERY")
            .all()
        )
        assert len(predictions) == 0
        mock_predict.assert_not_called()

        # 2. Ingest 10th telemetry message (prediction trigger expected)
        payload_10th = {
            "schema_version": "1.0",
            "source": "ev_simulator_local",
            "battery_id": "LSTM_TEST_BATTERY",
            "vehicle_id": "VH_TESLA_001",
            "timestamp": "2024-01-15T14:23:10.000Z",
            "cycle_number": 10,
            "cycle_type": "discharge",
            "measurements": {
                "voltage_v": 3.8,
                "current_a": -2.0,
                "temperature_c": 25.0,
                "capacity_mah": 1880.0,
            },
        }
        response = client.post(
            "/api/v1/ingest", json=payload_10th, headers=headers
        )
        assert response.status_code == 202

        # Verify predictions were calculated and written to DB
        mock_predict.assert_called_once()
        predictions = (
            db_session.query(RULPrediction)
            .filter_by(battery_id="LSTM_TEST_BATTERY")
            .all()
        )
        assert len(predictions) == 1
        assert predictions[0].predicted_rul_cycles == 213
        assert predictions[0].confidence_lower == 188
        assert predictions[0].confidence_upper == 238
        assert predictions[0].model_version == "v2.0"
        assert float(predictions[0].input_soh_percent) is not None
