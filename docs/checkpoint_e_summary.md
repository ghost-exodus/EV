# Checkpoint E — LSTM RUL Model Integration Summary

**Date**: 2026-06-18
**Author**: Backend Team (integration) + Data Ka Pandit (model training)
**Status**: Integration complete — pending joint verification

---

## 1. Model Input Format (Production)

The LSTM model receives a **sequence of 50 timesteps** with **5 features each**, MinMax-scaled to [0, 1].

### Feature Order (must match training)

| Index | Feature Name | Source in Backend | Mapping |
|-------|-------------|-------------------|---------|
| 0 | `voltage_mean` | `telemetry.voltage_v` | Direct (renamed) |
| 1 | `current_mean` | `telemetry.current_a` | Direct (renamed) |
| 2 | `temp_mean` | `telemetry.temperature_c` | Direct (renamed) |
| 3 | `capacity_mah` | `telemetry.capacity_mah` | Direct |
| 4 | `soh_percent` | `soh_snapshots.soh_percent` | **See approximation note below** |

### Input Shape
```
(1, 50, 5) — [batch_size=1, sequence_length=50, features=5]
```

### Scaling
- Features are scaled using the `MinMaxScaler` saved at `ml/models/scaler.pkl`
- The scaler was fitted on the NASA B0005 training data during `train_lstm.py`
- Output is inverse-scaled using the same pickle's `scaler_y`

### Sequence Construction
- Last 50 telemetry rows for the battery, ordered oldest → newest
- If fewer than 50 rows exist: padded by repeating the first row at the start
- If `capacity_mah` is null in a row: forward-filled from previous row, or fallback to 1800 mAh

---

## 2. API Output Format

### `GET /api/v1/rul/{battery_id}`

```json
{
  "battery_id": "BAT_001",
  "predicted_rul_cycles": 125,
  "confidence_interval": {
    "lower_bound": 113,
    "upper_bound": 137,
    "confidence_percent": 90.0
  },
  "current_soh_percent": 80.0,
  "eol_threshold_soh": 70.0,
  "model_version": "lstm_v1",
  "predicted_at": "2024-06-15T14:23:45.123Z",
  "alert_level": "none"
}
```

### Internal Prediction Dict (from `ml_service.predict_rul`)

```json
{
  "predicted_rul_cycles": 125,
  "confidence_lower": 113,
  "confidence_upper": 137,
  "model_version": "lstm_v1"
}
```

---

## 3. Known Approximations

> [!WARNING]
> ### SoH as a Constant Across the Sequence
>
> **Training data**: Each of the 50 timesteps in a sequence had its own per-cycle
> `soh_percent` value reflecting gradual degradation (e.g., 85.2, 85.1, 85.0, ...).
>
> **Production inference**: We use the **single latest** `soh_percent` value from
> `soh_snapshots` and repeat it across all 50 timesteps (e.g., 85.0, 85.0, 85.0, ...).
>
> **Impact**: This creates a distribution shift between training and inference.
> Since SoH changes slowly cycle-to-cycle (~0.1% per cycle), the model still
> produces reasonable output, but it's not a perfect match.
>
> **Recommended fix**: Either:
> 1. Store `soh_percent` per telemetry row going forward, or
> 2. Recompute historical SoH per row retroactively using
>    `(capacity_mah / nominal_capacity) * 100`
>
> **Decision needed from Data Ka Pandit at Checkpoint E.**

> [!NOTE]
> ### Confidence Bounds Are Approximations
>
> The LSTM produces a **point estimate only**. The confidence bounds reported
> by the API are `±10%` of the predicted value — not derived from model
> uncertainty quantification (e.g., MC dropout or ensemble variance).
>
> If proper uncertainty bounds are needed, Data Ka Pandit can:
> - Add MC Dropout to the LSTM and run N forward passes
> - Train an ensemble of models
> - Use a Bayesian LSTM variant

---

## 4. Model Artifacts

| File | Path | Size | Description |
|------|------|------|-------------|
| Model weights | `ml/models/rul_lstm_v1.pt` | 809 KB | PyTorch state_dict |
| Scalers | `ml/models/scaler.pkl` | 1.1 KB | MinMaxScaler for X and Y |

### Architecture
```
BatteryRULPredictorLSTM(
  (lstm): LSTM(5, 128, num_layers=2, batch_first=True)
  (fc): Linear(in_features=128, out_features=1)
)
```

---

## 5. Dependencies Added

| Package | Version | Purpose |
|---------|---------|---------|
| `torch` | >=2.0.0 (CPU-only) | LSTM inference |
| `scikit-learn` | >=1.3.0 | MinMaxScaler for feature scaling |
| `numpy` | >=1.26.0 | Array operations |
| `pandas` | >=2.1.0 | Required by scaler pickle |

---

## 6. Verification Results

### Isolated Test (Step 5)
- Model loaded: **YES**
- 50 readings, SoH=80%: predicted RUL = **125 cycles** [113, 137]
- 5 readings (padded): predicted RUL = **153 cycles** (padding works)
- Null capacity rows: predicted RUL = **124 cycles** (fallback works)
- Not stub values (213/188/238): **CONFIRMED**

### Full E2E Pipeline (Step 6)
- Model loaded in Docker container: **YES** (cold-start lazy loading succeeds within ~8s)
- Ingestion of 15 telemetry rows triggers background prediction task on the 10th row: **YES** (returns 202 Accepted, triggers background worker)
- Prediction stored in `rul_predictions` table: **YES**
- GET `/api/v1/rul/{battery_id}` serves prediction via JWT auth: **YES**
- Sensitivity & degradation validation: **YES**
  - Run 1 (SoH = 87.15%): Predicted RUL = **149 cycles** (confidence interval `[134, 164]`)
  - Run 2 (SoH = 80.00%): Predicted RUL = **128 cycles** (confidence interval `[115, 141]`)
  - RUL decreases cleanly as SoH/capacity degrades, confirming correct inputs are fed to the model.
- Model version registered: `lstm_v1` (not the old stub 'v2.0')

---

## 7. Questions for Data Ka Pandit

1. **Per-cycle SoH**: Should we backfill historical SoH per telemetry row to
   match training data distribution? (See Section 3)
2. **Feature name mapping**: We map `voltage_v → voltage_mean`. Your training
   data used per-cycle means from the NASA dataset. Our telemetry stores one
   reading per ingest. Is this equivalent to what you trained on?
3. **Confidence bounds**: Do you want to add proper uncertainty quantification
   (MC Dropout, ensembles), or are ±10% placeholder bounds acceptable for MVP?
4. **Scaler version**: The scaler was pickled with sklearn 1.9.0. Should we
   re-export it or pin to that version?
