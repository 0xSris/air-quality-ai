from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.data.dataset import TARGET_COLUMNS
from ml.training.base import ForecasterModel


class BaselineForecaster(ForecasterModel):
    name = "baseline_random_forest"

    def __init__(self, feature_columns: list[str], config: dict) -> None:
        self.feature_columns = feature_columns
        self.pipeline = Pipeline(
            steps=[
                (
                    "preprocess",
                    ColumnTransformer(
                        transformers=[
                            (
                                "numeric",
                                Pipeline(
                                    steps=[
                                        ("imputer", SimpleImputer(strategy="median")),
                                        ("scaler", StandardScaler()),
                                    ]
                                ),
                                feature_columns,
                            )
                        ]
                    ),
                ),
                (
                    "model",
                    MultiOutputRegressor(
                        RandomForestRegressor(
                            n_estimators=config.get("n_estimators", 300),
                            max_depth=config.get("max_depth", 14),
                            random_state=42,
                            n_jobs=1,
                        )
                    ),
                ),
            ]
        )

    def fit(self, train_frame: pd.DataFrame, validation_frame: pd.DataFrame) -> None:
        x_train = train_frame[self.feature_columns]
        y_train = train_frame[TARGET_COLUMNS]
        self.pipeline.fit(x_train, y_train)

    def predict(self, frame: pd.DataFrame):
        return self.pipeline.predict(frame[self.feature_columns])

    def save(self, output_dir: Path) -> None:
        joblib.dump(self.pipeline, output_dir / f"{self.name}.joblib")
