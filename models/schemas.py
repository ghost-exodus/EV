"""
Pydantic schemas for request validation and response serialization.

Covers:
  - IngestPayload:          POST /api/v1/ingest request body
  - IngestResponse:         POST /api/v1/ingest response
  - TelemetryReading:       Single reading in telemetry list
  - TelemetryResponse:      GET /api/v1/telemetry/{battery_id} response
  - SoHTrendEntry:          Single point in SoH trend history
  - SoHTrend:               Trend block inside SoH response
  - SoHResponse:            GET /api/v1/soh/{battery_id} response
  - FleetBatteryEntry:      Single battery overview in fleet summary
  - FleetSummaryResponse:   GET /api/v1/fleet/summary response
  - RULResponse:            GET /api/v1/rul/{battery_id} response
  - DegradationEntry:       Single point in degradation response
  - DegradationResponse:    GET /api/v1/analytics/degradation response
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# POST /api/v1/ingest
# ---------------------------------------------------------------------------


class Measurements(BaseModel):
    voltage_v: float = Field(
        ..., 
        description="Battery voltage in volts", 
        examples=[3.8124]
    )
    current_a: float = Field(
        ..., 
        description="Current in amps (negative indicates discharge, positive indicates charge)", 
        examples=[-1.9987]
    )
    temperature_c: float = Field(
        ..., 
        description="Temperature in Celsius", 
        examples=[24.5]
    )
    capacity_mah: Optional[float] = Field(
        None, 
        description="Measured/remaining capacity in mAh", 
        examples=[1823.4]
    )
    internal_resistance_ohm: Optional[float] = Field(
        None, 
        description="Internal resistance in ohms (accepted but not persisted)", 
        examples=[0.056]
    )


class Metadata(BaseModel):
    """Flexible metadata block — accepts any extra keys."""
    model_config = {"extra": "allow"}

    simulator_version: Optional[str] = Field(
        None, 
        description="Version of the simulator generating metrics", 
        examples=["1.2.0"]
    )
    replay_speed: Optional[float] = Field(
        None, 
        description="Speed factor of playback replay", 
        examples=[1.0]
    )
    source_file: Optional[str] = Field(
        None, 
        description="Original source file name", 
        examples=["00001.csv"]
    )


class IngestPayload(BaseModel):
    schema_version: Optional[str] = Field(
        None, 
        description="Data contract version", 
        examples=["1.0"]
    )
    source: Optional[str] = Field(
        None, 
        description="Data source identifier (e.g. simulator/operator)", 
        examples=["ev_simulator_aws"]
    )
    battery_id: str = Field(
        ..., 
        max_length=32, 
        description="Unique identifier for the battery pack", 
        examples=["B0047"]
    )
    vehicle_id: Optional[str] = Field(
        None, 
        max_length=64, 
        description="Associated vehicle ID", 
        examples=["VH_TESLA_042"]
    )
    timestamp: datetime = Field(
        ..., 
        description="Measurement timestamp in ISO 8601 format", 
        examples=["2026-06-13T17:03:00Z"]
    )
    cycle_number: int = Field(
        ..., 
        ge=0, 
        description="The battery test cycle index", 
        examples=[47]
    )
    cycle_type: Optional[str] = Field(
        "unknown", 
        max_length=16, 
        description="Operation type: 'charge' or 'discharge'", 
        examples=["discharge"]
    )
    measurements: Measurements
    metadata: Optional[Metadata] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "schema_version": "1.0",
                    "source": "ev_simulator_local",
                    "battery_id": "EV_B0005_001",
                    "vehicle_id": "VH_TESLA_042",
                    "timestamp": "2024-01-15T14:23:45.123Z",
                    "cycle_number": 147,
                    "cycle_type": "discharge",
                    "measurements": {
                        "voltage_v": 3.8124,
                        "current_a": -1.9987,
                        "temperature_c": 24.5,
                        "capacity_mah": 1823.4,
                        "internal_resistance_ohm": 0.0214
                    },
                    "metadata": {
                        "simulator_version": "1.0.0",
                        "replay_speed": 1.0,
                        "source_file": "B0005.csv"
                    }
                },
                {
                    "battery_id": "EV_B0005_001",
                    "timestamp": "2024-01-15T14:23:45.123Z",
                    "cycle_number": 147,
                    "cycle_type": "discharge",
                    "measurements": {
                        "voltage_v": 3.8124,
                        "current_a": -1.9987,
                        "temperature_c": 24.5,
                        "capacity_mah": 1823.4
                    }
                }
            ]
        }
    }


class IngestResponse(BaseModel):
    ingested: bool = Field(
        ..., 
        description="Indicates whether telemetry ingestion was successful", 
        examples=[True]
    )
    battery_id: str = Field(
        ..., 
        description="The battery ID associated with the ingested data", 
        examples=["B0047"]
    )


# ---------------------------------------------------------------------------
# SQS POST /api/v1/ingest (Phase 2 message format)
# ---------------------------------------------------------------------------


class MetadataV2(BaseModel):
    """Metadata block for SQS payloads — accepts any extra keys."""
    model_config = {"extra": "allow"}

    simulator_version: Optional[str] = Field(
        None, 
        description="Version of simulator generating telemetry", 
        examples=["2.0.0"]
    )
    aws_region: Optional[str] = Field(
        None, 
        description="AWS region where telemetry was published", 
        examples=["us-east-1"]
    )
    queue_name: Optional[str] = Field(
        None, 
        description="SQS queue name", 
        examples=["ev-telemetry.fifo"]
    )
    sqs_message_group_id: Optional[str] = Field(
        None, 
        description="SQS Message Group ID for ordering", 
        examples=["B0047"]
    )


class IngestPayloadV2(BaseModel):
    schema_version: str = Field(
        ..., 
        description="Data contract version (should be '2.0')", 
        examples=["2.0"]
    )
    source: str = Field(
        ..., 
        description="Data source identifier", 
        examples=["ev_simulator_aws"]
    )
    battery_id: str = Field(
        ..., 
        max_length=32, 
        description="Unique identifier of the battery", 
        examples=["B0047"]
    )
    vehicle_id: str = Field(
        ..., 
        max_length=64, 
        description="Associated vehicle identifier", 
        examples=["VH_TESLA_042"]
    )
    timestamp: datetime = Field(
        ..., 
        description="ISO 8601 timestamp of data capture", 
        examples=["2026-06-13T17:03:00Z"]
    )
    sequence_id: str = Field(
        ..., 
        description="Unique sequential identifier for order validation", 
        examples=["B0047_000147"]
    )
    cycle_number: int = Field(
        ..., 
        ge=0, 
        description="Cycle count", 
        examples=[147]
    )
    cycle_type: str = Field(
        ..., 
        max_length=16, 
        description="Operation: 'charge' or 'discharge'", 
        examples=["discharge"]
    )
    measurements: Measurements
    metadata: Optional[MetadataV2] = None


# ---------------------------------------------------------------------------
# GET /api/v1/telemetry/{battery_id}
# ---------------------------------------------------------------------------


class TelemetryReading(BaseModel):
    id: int = Field(
        ..., 
        description="Unique database entry ID", 
        examples=[23591]
    )
    recorded_at: datetime = Field(
        ..., 
        description="Timestamp of the measurement", 
        examples=["2026-06-13T17:03:00Z"]
    )
    cycle_number: int = Field(
        ..., 
        description="Cycle number during measurement", 
        examples=[47]
    )
    cycle_type: str = Field(
        ..., 
        description="Cycle type ('charge' or 'discharge')", 
        examples=["discharge"]
    )
    voltage_v: float = Field(
        ..., 
        description="Voltage reading (V)", 
        examples=[3.8124]
    )
    current_a: float = Field(
        ..., 
        description="Current reading (A)", 
        examples=[-1.9987]
    )
    temperature_c: float = Field(
        ..., 
        description="Temperature reading (°C)", 
        examples=[24.5]
    )
    capacity_mah: Optional[float] = Field(
        None, 
        description="Capacity calculation associated (mAh)", 
        examples=[1823.4]
    )


class TelemetryResponse(BaseModel):
    battery_id: str = Field(
        ..., 
        description="Battery ID queried", 
        examples=["B0047"]
    )
    total_records: int = Field(
        ..., 
        description="Total matching records found", 
        examples=[250]
    )
    cursor: Optional[str] = Field(
        None, 
        description="Pagination cursor for the next batch of readings", 
        examples=["1718293910.123"]
    )
    has_more: bool = Field(
        ..., 
        description="Indicates whether more historical pages exist", 
        examples=[False]
    )
    readings: list[TelemetryReading] = Field(
        ..., 
        description="List of telemetry data points"
    )


# ---------------------------------------------------------------------------
# GET /api/v1/soh/{battery_id}
# ---------------------------------------------------------------------------


class SoHTrendEntry(BaseModel):
    cycle: int = Field(
        ..., 
        description="Cycle number", 
        examples=[1]
    )
    soh_percent: float = Field(
        ..., 
        description="State of Health (SOH) calculated percent", 
        examples=[83.71]
    )
    snapshot_at: datetime = Field(
        ..., 
        description="Timestamp of the calculation snapshot", 
        examples=["2026-06-13T17:03:00Z"]
    )


class SoHTrend(BaseModel):
    direction: str = Field(
        ..., 
        description="SOH direction metric ('degrading', 'stable', or 'improving')", 
        examples=["degrading"]
    )
    delta_last_10_cycles: float = Field(
        ..., 
        description="Delta change in SOH over the last 10 cycles", 
        examples=[-1.25]
    )
    history: list[SoHTrendEntry] = Field(
        ..., 
        description="Historical SOH points"
    )


class SoHResponse(BaseModel):
    battery_id: str = Field(
        ..., 
        description="Battery identifier", 
        examples=["B0047"]
    )
    current_soh_percent: Optional[float] = Field(
        None, 
        description="Latest calculated SOH percent", 
        examples=[83.71]
    )
    status: str = Field(
        ..., 
        description="Health status label ('healthy', 'warning', or 'critical')", 
        examples=["healthy"]
    )
    nominal_capacity_mah: Optional[float] = Field(
        None, 
        description="Battery rated capacity in mAh", 
        examples=[2000.0]
    )
    current_capacity_mah: Optional[float] = Field(
        None, 
        description="Latest measured capacity in mAh", 
        examples=[1674.3]
    )
    last_calculated_at: Optional[datetime] = Field(
        None, 
        description="Timestamp of the calculation", 
        examples=["2026-06-13T17:03:00Z"]
    )
    trend: Optional[SoHTrend] = None
    message: Optional[str] = Field(
        None,
        description="Optional diagnostic/availability message",
        examples=["No SoH data available yet — capacity_mah not received"]
    )


# ---------------------------------------------------------------------------
# GET /api/v1/fleet/summary
# ---------------------------------------------------------------------------


class FleetBatteryEntry(BaseModel):
    battery_id: str = Field(
        ..., 
        description="Unique battery identifier", 
        examples=["B0047"]
    )
    vehicle_id: str = Field(
        ..., 
        description="Associated vehicle identification string", 
        examples=["VH_TESLA_042"]
    )
    current_soh_percent: Optional[float] = Field(
        None, 
        description="Current SOH percentage", 
        examples=[83.71]
    )
    predicted_rul_cycles: Optional[int] = Field(
        None, 
        description="Predicted remaining useful life cycles before failure", 
        examples=[213]
    )
    status: str = Field(
        ..., 
        description="Health status: 'healthy', 'warning', 'critical', or 'unknown'", 
        examples=["healthy"]
    )
    last_seen: Optional[datetime] = Field(
        None, 
        description="Timestamp of the last telemetry packet", 
        examples=["2026-06-13T17:03:00Z"]
    )


class StatusSummary(BaseModel):
    healthy: int = Field(
        ..., 
        description="Count of healthy batteries in fleet", 
        examples=[15]
    )
    warning: int = Field(
        ..., 
        description="Count of warning batteries in fleet", 
        examples=[3]
    )
    critical: int = Field(
        ..., 
        description="Count of critical batteries in fleet", 
        examples=[1]
    )


class FleetSummaryResponse(BaseModel):
    total_batteries: int = Field(
        ..., 
        description="Total batteries managed in fleet", 
        examples=[19]
    )
    status_summary: StatusSummary
    fleet_avg_soh_percent: Optional[float] = Field(
        None, 
        description="Average State of Health across the active fleet", 
        examples=[81.45]
    )
    batteries: list[FleetBatteryEntry] = Field(
        ..., 
        description="Details of all batteries in the fleet"
    )


# ---------------------------------------------------------------------------
# Week 6/7 Endpoints
# ---------------------------------------------------------------------------


class ConfidenceInterval(BaseModel):
    lower_bound: int = Field(
        ..., 
        description="Lower interval bound of RUL prediction", 
        examples=[188]
    )
    upper_bound: int = Field(
        ..., 
        description="Upper interval bound of RUL prediction", 
        examples=[238]
    )
    confidence_percent: float = Field(
        90.0, 
        description="Statistical confidence level percent", 
        examples=[90.0]
    )


class RULResponse(BaseModel):
    battery_id: str = Field(
        ..., 
        description="Battery pack ID", 
        examples=["B0047"]
    )
    status: str = Field(
        "ready",
        description="Prediction status: 'ready' or 'pending'",
        examples=["ready"]
    )
    predicted_rul_cycles: int = Field(
        ..., 
        description="LSTM predicted remaining cycles before EOL threshold is hit", 
        examples=[213]
    )
    confidence_interval: ConfidenceInterval
    current_soh_percent: float = Field(
        ..., 
        description="SOH percentage used for this prediction", 
        examples=[83.71]
    )
    eol_threshold_soh: float = Field(
        70.0, 
        description="SOH target threshold representing End Of Life", 
        examples=[70.0]
    )
    model_version: str = Field(
        ..., 
        description="Model definition version code", 
        examples=["v2.0"]
    )
    predicted_at: datetime = Field(
        ..., 
        description="Timestamp of prediction generation", 
        examples=["2026-06-13T17:03:00Z"]
    )
    alert_level: str = Field(
        ..., 
        description="Alert classification ('healthy', 'warning', or 'critical')", 
        examples=["healthy"]
    )


class RULPendingResponse(BaseModel):
    battery_id: str = Field(
        ...,
        description="Battery pack ID",
        examples=["B0047"]
    )
    status: str = Field(
        "pending",
        description="Prediction status: 'pending' — not yet available",
        examples=["pending"]
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of why the prediction is pending",
        examples=["RUL prediction not yet available — insufficient telemetry data ingested."]
    )


class DegradationEntry(BaseModel):
    date: str = Field(
        ..., 
        description="Calendar date of health state", 
        examples=["2026-06-13"]
    )
    avg_soh_percent: float = Field(
        ..., 
        description="Average SOH on this date", 
        examples=[83.71]
    )
    min_soh_percent: float = Field(
        ..., 
        description="Lowest single SOH snapshot on this date", 
        examples=[83.71]
    )


class DegradationResponse(BaseModel):
    battery_id: str = Field(
        ..., 
        description="Battery ID queried", 
        examples=["B0047"]
    )
    data: list[DegradationEntry] = Field(
        ..., 
        description="Daily history entries of SOH degradation"
    )


# ---------------------------------------------------------------------------
# Error Response
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: str = Field(
        ..., 
        description="Error description message", 
        examples=["Rate limit exceeded"]
    )
