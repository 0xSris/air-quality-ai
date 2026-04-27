from __future__ import annotations

import json
from functools import cached_property

import pandas as pd

from backend.app.core.config import Settings


class DataRepository:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def train_features(self) -> pd.DataFrame:
        return pd.read_parquet(self.settings.processed_data_dir / "train_features.parquet")

    @cached_property
    def unseen_features(self) -> pd.DataFrame:
        return pd.read_parquet(self.settings.processed_data_dir / "unseen_features.parquet")

    @cached_property
    def dataset_summary(self) -> dict:
        return json.loads((self.settings.processed_data_dir / "dataset_summary.json").read_text(encoding="utf-8"))

    @cached_property
    def metadata(self) -> dict:
        return json.loads((self.settings.artifacts_dir / "metadata.json").read_text(encoding="utf-8"))

    def site_summary(self, site_id: int) -> dict:
        for site in self.dataset_summary["sites"]:
            if site["site_id"] == site_id:
                return site
        raise KeyError(f"Unknown site_id {site_id}")

    def model_feature_columns(self, model_name: str) -> list[str]:
        model_columns = self.metadata.get("model_feature_columns", {})
        if model_name in model_columns:
            return model_columns[model_name]
        return self.metadata.get("feature_columns", [])

    def site_frame(self, site_id: int, split: str = "train") -> pd.DataFrame:
        frame = self.train_features if split == "train" else self.unseen_features
        site_frame = frame.loc[frame["site_id"] == site_id].copy()
        site_frame["timestamp"] = pd.to_datetime(site_frame["timestamp"])
        return site_frame.sort_values("timestamp").reset_index(drop=True)
