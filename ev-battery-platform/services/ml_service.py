"""
ML Service — Real LSTM RUL Prediction Adapter.

Replaces the former stub with a real PyTorch LSTM model loaded from
ml/models/rul_lstm_v1.pt + ml/models/scaler.pkl (trained by Data Ka Pandit).

Design decisions:
  - Model + scalers are loaded ONCE via a lazy singleton (not per-request).
  - predict_rul() signature matches the existing contract so ingest_service.py
    needs only a minimal change (passing soh_percent).
  - Confidence bounds are ±10% approximations — the LSTM produces a point
    estimate only. Flagged clearly for Checkpoint E review.
  - All inference errors are caught and logged; the background task never crashes.
"""

import logging
import os
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("ml_service")

# ── Paths to model artifacts (relative to project root /app in Docker) ────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MODEL_PATH = _PROJECT_ROOT / "ml" / "models" / "rul_lstm_v1.pt"
_SCALER_PATH = _PROJECT_ROOT / "ml" / "models" / "scaler.pkl"

# Feature order must match train_lstm.py exactly
_FEATURE_COLS = ["voltage_mean", "current_mean", "temp_mean", "capacity_mah", "soh_percent"]
_SEQUENCE_LENGTH = 50
_MODEL_VERSION = "lstm_v1"

# Fallback values for missing data (based on NASA B0005 typical ranges)
_FALLBACK_CAPACITY_MAH = 1800.0
_FALLBACK_SOH_PERCENT = 100.0


# ── Lazy Singleton: load model + scalers once on first prediction call ────────

class _ModelSingleton:
    """
    Holds the PyTorch model and sklearn scalers in memory.
    Loaded lazily on first call to .get() so the FastAPI app starts
    even if model files are missing (logs a clear error instead of crashing).
    """

    _instance: Optional["_ModelSingleton"] = None
    _loaded: bool = False

    def __init__(self):
        self.model = None
        self.scaler_x = None
        self.scaler_y = None

    @classmethod
    def get(cls) -> "_ModelSingleton":
        if cls._instance is None:
            cls._instance = cls()
        if not cls._instance._loaded:
            cls._instance._load()
        return cls._instance

    def _load(self):
        """Load PyTorch model weights and sklearn scalers from disk."""
        try:
            import torch
            # Import the model class definition from the training script
            # We inline it here to avoid running train_lstm.py's top-level code
            # (which reads CSVs and trains the model).
            import torch.nn as nn

            class BatteryRULPredictorLSTM(nn.Module):
                """Mirror of the architecture in ml/train_lstm.py."""
                def __init__(self, input_size=5, hidden_size=128, num_layers=2, output_size=1):
                    super().__init__()
                    self.hidden_size = hidden_size
                    self.num_layers = num_layers
                    self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
                    self.fc = nn.Linear(hidden_size, output_size)

                def forward(self, x):
                    h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
                    c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
                    out, _ = self.lstm(x, (h0, c0))
                    out = self.fc(out[:, -1, :])
                    return out

            # Load model weights
            if not _MODEL_PATH.exists():
                logger.error(f"Model file not found at {_MODEL_PATH}. Predictions will use fallback.")
                self._loaded = True
                return

            self.model = BatteryRULPredictorLSTM()
            state_dict = torch.load(_MODEL_PATH, map_location="cpu", weights_only=True)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            logger.info(f"LSTM model loaded successfully from {_MODEL_PATH}")

            # Load scalers
            if not _SCALER_PATH.exists():
                logger.error(f"Scaler file not found at {_SCALER_PATH}. Predictions will use fallback.")
                self.model = None  # Can't run inference without scalers
                self._loaded = True
                return

            with open(_SCALER_PATH, "rb") as f:
                scalers = pickle.load(f)
            self.scaler_x = scalers["scaler_x"]
            self.scaler_y = scalers["scaler_y"]
            logger.info(f"Scalers loaded successfully from {_SCALER_PATH}")

            self._loaded = True

        except Exception as e:
            logger.error(f"Failed to load ML model/scalers: {e}", exc_info=True)
            self.model = None
            self.scaler_x = None
            self.scaler_y = None
            self._loaded = True  # Don't retry every request; fail fast with fallback


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_feature_array(
    recent_readings: list[dict],
    soh_percent: Optional[float],
) -> np.ndarray:
    """
    Transform the list of telemetry dicts into a (N, 5) numpy array
    matching the training feature order.

    Handles:
      - Column name mapping (voltage_v → voltage_mean, etc.)
      - Null capacity_mah (forward-fill, then fallback)
      - Missing soh_percent (constant fill with latest or fallback)
      - Padding to 50 rows if fewer readings exist
    """
    soh = soh_percent if soh_percent is not None else _FALLBACK_SOH_PERCENT
    if soh_percent is None:
        logger.warning(
            "soh_percent not provided to predict_rul; using fallback %.1f%%. "
            "This may reduce prediction accuracy.",
            _FALLBACK_SOH_PERCENT,
        )

    rows = []
    last_good_capacity = None

    for r in recent_readings:
        # Map backend column names → training feature names
        voltage = float(r.get("voltage_v", 0.0))
        current = float(r.get("current_a", 0.0))
        temp = float(r.get("temperature_c", 0.0))

        # Handle null capacity_mah: forward-fill from previous row
        cap_raw = r.get("capacity_mah")
        if cap_raw is not None:
            capacity = float(cap_raw)
            last_good_capacity = capacity
        elif last_good_capacity is not None:
            capacity = last_good_capacity
            logger.debug("capacity_mah is null in reading, forward-filled from previous row.")
        else:
            capacity = _FALLBACK_CAPACITY_MAH
            logger.warning(
                "capacity_mah is null and no previous value available; "
                "using fallback %.1f mAh.",
                _FALLBACK_CAPACITY_MAH,
            )

        # SoH: use the single latest value for all timesteps
        # NOTE: This is a documented approximation — the model was trained on
        # per-cycle SoH values. See Checkpoint E summary for discussion.
        rows.append([voltage, current, temp, capacity, soh])

    features = np.array(rows, dtype=np.float64)

    # Pad to _SEQUENCE_LENGTH if fewer readings available
    actual_len = len(features)
    if actual_len < _SEQUENCE_LENGTH:
        logger.warning(
            "Only %d readings available (model expects %d). "
            "Padding by repeating the first reading. Prediction may be less accurate.",
            actual_len,
            _SEQUENCE_LENGTH,
        )
        pad_count = _SEQUENCE_LENGTH - actual_len
        padding = np.tile(features[0:1, :], (pad_count, 1))  # repeat first row
        features = np.vstack([padding, features])  # pad at the START (oldest end)

    # If somehow more than 50, take the last 50 (most recent window)
    if len(features) > _SEQUENCE_LENGTH:
        features = features[-_SEQUENCE_LENGTH:]

    return features


def _fallback_prediction() -> dict:
    """Return a safe fallback when the model can't run."""
    return {
        "predicted_rul_cycles": 0,
        "confidence_lower": 0,
        "confidence_upper": 0,
        "model_version": "unavailable",
    }


# ── Public API (matches the existing contract) ───────────────────────────────

def predict_rul(
    battery_id: str,
    recent_readings: list[dict],
    soh_percent: Optional[float] = None,
) -> dict:
    """
    Predict Remaining Useful Life (RUL) cycles based on recent telemetry.

    This function maintains backward compatibility with the original stub
    signature, with an added optional soh_percent parameter.

    Input:
      battery_id:      string identifier (logged, not used by model)
      recent_readings: list of dicts with keys: voltage_v, current_a,
                       temperature_c, capacity_mah (up to 50 rows,
                       oldest → newest)
      soh_percent:     latest SoH value from soh_snapshots table (optional)

    Output:
      dict with keys: predicted_rul_cycles (int), confidence_lower (int),
                      confidence_upper (int), model_version (str)
    """
    try:
        singleton = _ModelSingleton.get()

        if singleton.model is None or singleton.scaler_x is None or singleton.scaler_y is None:
            logger.error(
                "ML model or scalers not loaded. Returning fallback prediction "
                "for battery %s.",
                battery_id,
            )
            return _fallback_prediction()

        if not recent_readings:
            logger.warning(
                "Empty recent_readings for battery %s. Returning fallback.",
                battery_id,
            )
            return _fallback_prediction()

        # 1. Build (N, 5) feature array with column mapping + edge case handling
        features = _build_feature_array(recent_readings, soh_percent)

        # 2. Scale using the training-time MinMaxScaler
        features_scaled = singleton.scaler_x.transform(features)

        # 3. Reshape to (1, 50, 5) PyTorch tensor
        import torch
        input_tensor = torch.tensor(
            features_scaled.reshape(1, _SEQUENCE_LENGTH, len(_FEATURE_COLS)),
            dtype=torch.float32,
        )

        # 4. Run inference (no gradient computation needed)
        with torch.no_grad():
            raw_output = singleton.model(input_tensor)

        # 5. Inverse-scale the prediction back to real RUL cycles
        raw_value = raw_output.numpy().reshape(-1, 1)
        rul_unscaled = singleton.scaler_y.inverse_transform(raw_value)[0, 0]

        # 6. Sanity clamp: RUL must be non-negative
        if np.isnan(rul_unscaled) or np.isinf(rul_unscaled):
            logger.warning(
                "Model returned NaN/Inf for battery %s. Returning fallback.",
                battery_id,
            )
            return _fallback_prediction()

        predicted_rul = max(0, int(round(rul_unscaled)))

        # 7. Confidence bounds: ±10% approximation
        # NOTE: The LSTM produces a point estimate only. These bounds are a
        # placeholder — not derived from model uncertainty quantification.
        # This is flagged for Checkpoint E review with Data Ka Pandit.
        margin = max(1, int(round(predicted_rul * 0.10)))
        confidence_lower = max(0, predicted_rul - margin)
        confidence_upper = predicted_rul + margin

        logger.info(
            "LSTM prediction for battery %s: RUL=%d cycles [%d, %d] (model=%s)",
            battery_id,
            predicted_rul,
            confidence_lower,
            confidence_upper,
            _MODEL_VERSION,
        )

        return {
            "predicted_rul_cycles": predicted_rul,
            "confidence_lower": confidence_lower,
            "confidence_upper": confidence_upper,
            "model_version": _MODEL_VERSION,
        }

    except Exception as e:
        # Per Issue #4: never let a model error crash the background task
        logger.error(
            "Unhandled exception during RUL prediction for battery %s: %s",
            battery_id,
            e,
            exc_info=True,
        )
        return _fallback_prediction()
