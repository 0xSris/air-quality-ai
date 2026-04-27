from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ml.data.dataset import FEATURE_COLUMNS, TARGET_COLUMNS
from ml.data.external_sources import EXTERNAL_FEATURE_COLUMNS


@dataclass(slots=True)
class FeatureArtifacts:
    feature_columns: list[str]
    target_columns: list[str]


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    hour_angle = 2 * np.pi * out["hour"] / 24.0
    day_of_year = out["timestamp"].dt.dayofyear
    doy_angle = 2 * np.pi * day_of_year / 366.0
    out["hour_sin"] = np.sin(hour_angle)
    out["hour_cos"] = np.cos(hour_angle)
    out["doy_sin"] = np.sin(doy_angle)
    out["doy_cos"] = np.cos(doy_angle)
    out["is_weekend"] = out["timestamp"].dt.dayofweek.isin([5, 6]).astype(int)
    return out


def add_satellite_flags(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    sparse_columns = ["NO2_satellite", "HCHO_satellite", "ratio_satellite", *EXTERNAL_FEATURE_COLUMNS]
    additions: dict[str, pd.Series] = {}
    for col in sparse_columns:
        if col not in out.columns:
            continue
        additions[f"{col}_missing"] = out[col].isna().astype(int)
        out.loc[:, col] = out.groupby("site_id")[col].transform(lambda s: s.ffill().bfill()).fillna(0.0)
    if not additions:
        return out
    return pd.concat([out, pd.DataFrame(additions, index=out.index)], axis=1)


def add_lag_features(df: pd.DataFrame, lookback_hours: int) -> pd.DataFrame:
    out = df.copy()
    lag_steps = [1, 3, 6, 12, 24, 48, 72, min(lookback_hours, 168)]
    lag_columns = [*FEATURE_COLUMNS[:7], *[col for col in EXTERNAL_FEATURE_COLUMNS if col in out.columns]]
    additions: dict[str, pd.Series] = {}
    for col in lag_columns:
        for lag in sorted(set(lag_steps)):
            additions[f"{col}_lag_{lag}"] = out.groupby("site_id")[col].shift(lag)
    for col in lag_columns:
        for window in [6, 24, 72]:
            grouped = out.groupby("site_id")[col]
            additions[f"{col}_roll_mean_{window}"] = grouped.shift(1).rolling(window=window, min_periods=1).mean()
            additions[f"{col}_roll_std_{window}"] = (
                grouped.shift(1).rolling(window=window, min_periods=1).std().fillna(0.0)
            )
    if not additions:
        return out
    return pd.concat([out, pd.DataFrame(additions, index=out.index)], axis=1)


def build_features(
    df: pd.DataFrame, lookback_hours: int, target_columns: list[str] | None = None
) -> tuple[pd.DataFrame, FeatureArtifacts]:
    features = add_time_features(df)
    features = add_satellite_flags(features)
    features = add_lag_features(features, lookback_hours)
    target_columns = target_columns or [col for col in TARGET_COLUMNS if col in features.columns]
    target_columns = [col for col in target_columns if col in features.columns]
    feature_candidate_columns = [col for col in features.columns if col not in target_columns]
    non_target_mask = features[feature_candidate_columns].notna().all(axis=1)
    if target_columns:
        target_mask = features[target_columns].notna().all(axis=1)
        unseen_mask = features.get("dataset_split", pd.Series("train", index=features.index)).eq("unseen")
        keep_mask = non_target_mask & (target_mask | unseen_mask)
    else:
        keep_mask = non_target_mask
    features = features.loc[keep_mask].reset_index(drop=True)
    excluded = {"dataset_split", "timestamp", "year", "month", "day", "hour", "data_source"}
    feature_columns = [
        col
        for col in features.columns
        if col not in excluded and col not in target_columns and pd.api.types.is_numeric_dtype(features[col])
    ]
    return features, FeatureArtifacts(feature_columns=feature_columns, target_columns=target_columns)
