from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib


class ArtifactRegistry:
    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir
        self.metadata = json.loads((artifacts_dir / "metadata.json").read_text(encoding="utf-8"))

    def load_model(self, model_name: str, device: str = "cpu") -> Any:
        if model_name == "baseline_random_forest":
            return joblib.load(self.artifacts_dir / f"{model_name}.joblib")
        if model_name == "lstm":
            import torch

            from ml.training.sequence import LSTMForecaster

            payload = torch.load(self.artifacts_dir / "lstm.pt", map_location=device)
            model = LSTMForecaster(
                feature_columns=payload["feature_columns"],
                lookback_hours=payload["lookback_hours"],
                config=payload["config"],
                device=device,
            )
            model.model.load_state_dict(payload["state_dict"])
            model.residual_std = payload["residual_std"]
            model.artifacts.feature_imputer = payload["feature_imputer"]
            model.artifacts.feature_scaler = payload["feature_scaler"]
            model.artifacts.target_scaler = payload["target_scaler"]
            return model
        raise KeyError(f"Unknown model: {model_name}")
