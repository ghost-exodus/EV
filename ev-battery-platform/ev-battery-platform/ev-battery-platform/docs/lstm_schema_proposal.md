# LSTM Remaining Useful Life (RUL) Prediction Schema Proposal

This document outlines the proposed data contract between the FastAPI backend and the LSTM model serving service (Data Ka Pandit's `predict_rul()` function).

## 1. Overview
The LSTM model predicts the Remaining Useful Life (RUL) in charge/discharge cycles for a given battery. The prediction is computed using a sliding history of the last **50 telemetry readings** for the battery.

---

## 2. Input Schema: `RULPredictionInput`

The FastAPI backend will query the last 50 telemetry readings ordered by time ascending (`recorded_at ASC`) and compute statistical aggregates to pass to the LSTM service.

### JSON Structure
```json
{
  "battery_id": "EV_B0005_001",
  "history": [
    {
      "recorded_at": "2024-01-15T14:23:45.123Z",
      "cycle_number": 147,
      "cycle_type": "discharge",
      "voltage_v": 3.8124,
      "current_a": -1.9987,
      "temperature_c": 24.50,
      "capacity_mah": 1823.40,
      "soh_percent": 91.17
    }
  ],
  "features_aggregated": {
    "voltage_mean": 3.8152,
    "current_mean": -1.9912,
    "temp_mean": 24.58,
    "capacity_latest": 1823.40,
    "soh_delta_last_50_cycles": -1.82
  }
}
```

### Fields Description

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `battery_id` | `string` | Unique identifier for the EV battery. |
| `history` | `array[object]` | List of the last 50 chronological telemetry readings. |
| `history[].recorded_at` | `string (ISO 8601)` | Timestamp of the telemetry reading. |
| `history[].cycle_number` | `integer` | Operational cycle count. |
| `history[].cycle_type` | `string` | `'charge'` or `'discharge'`. |
| `history[].voltage_v` | `float` | Battery voltage in volts. |
| `history[].current_a` | `float` | Current in amps. |
| `history[].temperature_c` | `float` | Temperature in Celsius. |
| `history[].capacity_mah` | `float` | Measured capacity in mAh. |
| `history[].soh_percent` | `float` | Calculated State of Health percentage. |
| `features_aggregated` | `object` | Aggregated features computed over the window of 50 readings. |
| `features_aggregated.voltage_mean` | `float` | Mean voltage over the last 50 readings. |
| `features_aggregated.current_mean` | `float` | Mean current over the last 50 readings. |
| `features_aggregated.temp_mean` | `float` | Mean temperature over the last 50 readings. |
| `features_aggregated.capacity_latest` | `float` | The capacity from the latest cycle. |
| `features_aggregated.soh_delta_last_50_cycles` | `float` | Difference in SoH percent between the oldest and newest records in the window. |

---

## 3. Output Schema: `RULPredictionOutput`

The LSTM service returns the predicted cycles and confidence boundaries.

### JSON Structure
```json
{
  "predicted_rul_cycles": 320,
  "confidence_lower": 290,
  "confidence_upper": 350,
  "model_version": "lstm_v1.2.0"
}
```

### Fields Description

| Field Name | Type | Description |
| :--- | :--- | :--- |
| `predicted_rul_cycles` | `integer` | Estimated number of remaining cycles before battery capacity drops to critical threshold (typically < 80% or 70%). |
| `confidence_lower` | `integer` | Lower boundary of the 95% confidence interval for RUL cycles. |
| `confidence_upper` | `integer` | Upper boundary of the 95% confidence interval for RUL cycles. |
| `model_version` | `string` | Version tag of the deployed LSTM model used for this inference. |
