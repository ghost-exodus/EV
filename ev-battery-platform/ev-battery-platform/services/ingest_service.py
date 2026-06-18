"""
Shared ingestion service to handle core telemetry DB writes,
SoH calculation, and LSTM model prediction execution.
"""

import logging
from collections import defaultdict
import threading
from sqlalchemy.orm import Session

import time
import structlog
from db.models import Battery, Telemetry, SoHSnapshot, RULPrediction
from db.session import SessionLocal
from services.soh_service import _calculate_soh_with_session
from services.ml_service import predict_rul

logger = logging.getLogger("ingest_service")
ingest_logger = structlog.get_logger().bind(logger="ingest")

# Thread-safe in-memory message counter (resets on app restart)
in_memory_counter = defaultdict(int)
counter_lock = threading.Lock()

DEFAULT_NOMINAL_CAPACITY_MAH = 2000.0


def run_lstm_prediction_task(battery_id: str) -> None:
    """
    Fetch last 50 telemetry records, perform LSTM RUL prediction,
    and save the result to the database.
    
    Creates its own DB session so it can run safely in a BackgroundTask.
    """
    db = SessionLocal()
    try:
        # 1. Fetch last 50 telemetry readings (descending, then reversed to ascending/chronological order)
        readings_desc = (
            db.query(Telemetry)
            .filter(Telemetry.battery_id == battery_id)
            .order_by(Telemetry.recorded_at.desc())
            .limit(50)
            .all()
        )
        if not readings_desc:
            logger.warning(f"No telemetry readings found for {battery_id} during LSTM run.")
            return

        recent_readings = [
            {
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
                "cycle_number": r.cycle_number,
                "voltage_v": float(r.voltage_v),
                "current_a": float(r.current_a),
                "temperature_c": float(r.temperature_c),
                "capacity_mah": float(r.capacity_mah) if r.capacity_mah else None,
                "cycle_type": r.cycle_type,
            }
            for r in reversed(readings_desc)
        ]

        # 2. Fetch latest SoH snapshot to log the input health status
        latest_soh = (
            db.query(SoHSnapshot)
            .filter(SoHSnapshot.battery_id == battery_id)
            .order_by(SoHSnapshot.cycle_number.desc())
            .first()
        )
        soh_val = float(latest_soh.soh_percent) if latest_soh else None

        # 3. Call predictive model
        prediction_res = predict_rul(battery_id, recent_readings)

        # 4. Insert into the database
        pred_row = RULPrediction(
            battery_id=battery_id,
            predicted_rul_cycles=prediction_res["predicted_rul_cycles"],
            confidence_lower=prediction_res["confidence_lower"],
            confidence_upper=prediction_res["confidence_upper"],
            model_version=prediction_res["model_version"],
            input_soh_percent=soh_val,
        )
        db.add(pred_row)
        db.commit()
        logger.info(f"LSTM prediction written for battery {battery_id}: {prediction_res['predicted_rul_cycles']} cycles")
    except Exception as e:
        db.rollback()
        logger.error(f"Error executing LSTM background task for {battery_id}: {e}", exc_info=True)
    finally:
        db.close()


def ingest_telemetry_shared(payload, db: Session, background_tasks=None, source: str = "http") -> str:
    """
    Core ingestion flow used by both HTTP POST and SQS poller.
    Registers battery, logs telemetry, triggers SoH and RUL prediction checks.
    """
    start_time = time.perf_counter()

    # 1. Ensure battery registry entry exists
    battery = db.query(Battery).filter(Battery.battery_id == payload.battery_id).first()
    if battery is None:
        battery = Battery(
            battery_id=payload.battery_id,
            vehicle_id=payload.vehicle_id or "UNKNOWN",
            nominal_capacity_mah=DEFAULT_NOMINAL_CAPACITY_MAH,
        )
        db.add(battery)
        db.flush()

    # 2. Insert telemetry row
    reading = Telemetry(
        battery_id=payload.battery_id,
        recorded_at=payload.timestamp,
        cycle_number=payload.cycle_number,
        voltage_v=payload.measurements.voltage_v,
        current_a=payload.measurements.current_a,
        temperature_c=payload.measurements.temperature_c,
        capacity_mah=payload.measurements.capacity_mah,
        cycle_type=payload.cycle_type,
        internal_resistance_ohm=payload.measurements.internal_resistance_ohm,
    )
    db.add(reading)
    db.commit()

    # 3. Calculate SoH synchronously using the same session to measure total latency
    soh_value = None
    try:
        soh_value = _calculate_soh_with_session(payload.battery_id, db)
    except Exception as e:
        logger.error(f"Error in synchronous calculate_soh for {payload.battery_id}: {e}")

    # 4. Thread-safe increment of per-battery counter
    with counter_lock:
        in_memory_counter[payload.battery_id] += 1
        current_count = in_memory_counter[payload.battery_id]

    # Trigger LSTM analysis every 10th message
    if current_count % 10 == 0:
        if background_tasks is not None:
            background_tasks.add_task(run_lstm_prediction_task, payload.battery_id)
        else:
            # Run in worker executor thread to avoid blocking SQS poller event loop
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, run_lstm_prediction_task, payload.battery_id)
            except RuntimeError:
                # Fallback to direct call if no loop is running
                run_lstm_prediction_task(payload.battery_id)

    # 5. Measure latency and log JSON format via structlog
    latency_ms = (time.perf_counter() - start_time) * 1000.0
    ingest_logger.info(
        "telemetry_ingested",
        battery_id=payload.battery_id,
        latency_ms=round(latency_ms, 2),
        soh_value=soh_value,
        cycle_number=payload.cycle_number,
        source=source,
    )

    return payload.battery_id
