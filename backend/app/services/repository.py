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

    def site_frame(
        self,
        site_id: int,
        split: str = "train",
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        path = self.settings.processed_data_dir / (
            "train_features.parquet" if split == "train" else "unseen_features.parquet"
        )
        requested_columns = self._columns_with_required(columns)
        try:
            site_frame = pd.read_parquet(
                path,
                columns=requested_columns,
                filters=[("site_id", "=", site_id)],
            )
        except Exception:
            # Some parquet engines do not support predicate pushdown consistently.
            # Keep this fallback narrow by still reading only the columns needed.
            frame = pd.read_parquet(path, columns=requested_columns)
            site_frame = frame.loc[frame["site_id"] == site_id].copy()
        site_frame["timestamp"] = pd.to_datetime(site_frame["timestamp"])
        return site_frame.sort_values("timestamp").reset_index(drop=True)

    def observation_frame(self, site_id: int, split: str = "train") -> pd.DataFrame:
        return self.site_frame(
            site_id,
            split=split,
            columns=["timestamp", "site_id", "O3_target", "NO2_target"],
        )

    def forecast_input_frame(self, site_id: int) -> pd.DataFrame:
        return self.site_frame(
            site_id,
            split="unseen",
            columns=["timestamp", "site_id", "O3_forecast", "NO2_forecast"],
        )

    @staticmethod
    def _columns_with_required(columns: list[str] | None) -> list[str] | None:
        if columns is None:
            return None
        ordered = ["timestamp", "site_id", *columns]
        return list(dict.fromkeys(ordered))
