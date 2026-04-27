from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

from ml.data.dataset import DatasetLoader, FEATURE_COLUMNS, TARGET_COLUMNS
from ml.data.augmentation import ExternalFeatureAugmentor
from ml.data.external_sources import EXTERNAL_FEATURE_COLUMNS
from ml.data.validation import validate_dataframe
from ml.evaluation.metrics import regression_metrics
from ml.features.engineering import build_features
from ml.training.baseline import BaselineForecaster
from ml.training.sequence import LSTMForecaster
from ml.training.split import temporal_split


class TrainingPipeline:
    def __init__(
        self,
        raw_data_dir: Path,
        processed_dir: Path,
        artifacts_dir: Path,
        config_path: Path,
        settings,
        device: str = "cpu",
    ) -> None:
        self.raw_data_dir = raw_data_dir
        self.processed_dir = processed_dir
        self.artifacts_dir = artifacts_dir
        self.config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.settings = settings
        self.device = device
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def run(self, *, use_external_features: bool = False, refresh_external: bool = False) -> dict:
        bundle = DatasetLoader(self.raw_data_dir).load()
        if use_external_features:
            augmentor = ExternalFeatureAugmentor(self.settings)
            bundle.train, bundle.unseen = augmentor.augment(
                bundle.train,
                bundle.unseen,
                refresh=refresh_external,
            )
        train_report = validate_dataframe(bundle.train, require_targets=True)
        unseen_report = validate_dataframe(bundle.unseen, require_targets=False)
        if not train_report.passed or not unseen_report.passed:
            raise ValueError({"train": train_report.issues, "unseen": unseen_report.issues})

        combined = (
            pd.concat([bundle.train, bundle.unseen], ignore_index=True, sort=False)
            .sort_values(["site_id", "timestamp"])
            .reset_index(drop=True)
        )
        engineered_all, feature_artifacts = build_features(combined, self.config["lookback_hours"])
        engineered = engineered_all.loc[engineered_all["dataset_split"] == "train"].reset_index(drop=True)
        unseen_engineered = engineered_all.loc[engineered_all["dataset_split"] == "unseen"].reset_index(drop=True)
        splits = temporal_split(
            engineered,
            validation_fraction=self.config["validation_fraction"],
            test_fraction=self.config["test_fraction"],
        )
        self._save_processed(engineered, unseen_engineered, bundle.summary)

        baseline = BaselineForecaster(feature_artifacts.feature_columns, self.config["baseline"])
        baseline.fit(splits["train"], splits["validation"])
        baseline_pred = baseline.predict(splits["test"])

        sequence_feature_columns = [
            "site_id",
            "latitude",
            "longitude",
            *FEATURE_COLUMNS,
            *[col for col in EXTERNAL_FEATURE_COLUMNS if col in engineered.columns],
            "hour_sin",
            "hour_cos",
            "doy_sin",
            "doy_cos",
            "is_weekend",
            "NO2_satellite_missing",
            "HCHO_satellite_missing",
            "ratio_satellite_missing",
            *[f"{col}_missing" for col in EXTERNAL_FEATURE_COLUMNS if f"{col}_missing" in engineered.columns],
        ]
        lstm = LSTMForecaster(
            sequence_feature_columns,
            self.config["lookback_hours"],
            self.config["deep"],
            device=self.device,
        )
        lstm.fit(splits["train"], splits["validation"])
        lstm_pred = lstm.predict(splits["test"])
        lstm_truth = splits["test"][TARGET_COLUMNS].tail(len(lstm_pred)).to_numpy()

        metrics = {
            baseline.name: regression_metrics(
                splits["test"][TARGET_COLUMNS].to_numpy(), baseline_pred, TARGET_COLUMNS
            ),
            lstm.name: regression_metrics(lstm_truth, lstm_pred, TARGET_COLUMNS),
        }
        baseline.save(self.artifacts_dir)
        lstm.save(self.artifacts_dir)
        active_model = self._select_active_model(metrics)
        metadata = {
            "active_model": active_model,
            "available_models": [baseline.name, lstm.name],
            "metrics": metrics,
            "feature_columns": sequence_feature_columns,
            "model_feature_columns": {
                baseline.name: feature_artifacts.feature_columns,
                lstm.name: sequence_feature_columns,
            },
            "training_data_sources": self._training_sources(use_external_features),
            "external_feature_columns": [col for col in EXTERNAL_FEATURE_COLUMNS if col in engineered.columns],
            "targets": TARGET_COLUMNS,
            "config": self.config,
        }
        (self.artifacts_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return metadata

    def _save_processed(self, train: pd.DataFrame, unseen: pd.DataFrame, summary: dict) -> None:
        train.to_parquet(self.processed_dir / "train_features.parquet", index=False)
        unseen.to_parquet(self.processed_dir / "unseen_features.parquet", index=False)
        (self.processed_dir / "dataset_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    @staticmethod
    def _training_sources(use_external_features: bool) -> list[str]:
        sources = ["SIH provided site-level historical training dataset"]
        if use_external_features:
            sources.append(
                "Open-Meteo auxiliary air-quality context joined as exogenous features where external history is available"
            )
        return sources

    @staticmethod
    def _select_active_model(metrics: dict) -> str:
        def average_rmse(model_metrics: dict) -> float:
            values = [target_metrics["rmse"] for target_metrics in model_metrics.values()]
            return sum(values) / len(values)

        return min(metrics.keys(), key=lambda name: average_rmse(metrics[name]))
