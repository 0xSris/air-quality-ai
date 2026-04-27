from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ml.data.dataset import FEATURE_COLUMNS, TARGET_COLUMNS, TEMPORAL_COLUMNS


@dataclass(slots=True)
class ValidationReport:
    passed: bool
    issues: list[str]


def validate_dataframe(df: pd.DataFrame, require_targets: bool) -> ValidationReport:
    issues: list[str] = []
    required = set(TEMPORAL_COLUMNS + FEATURE_COLUMNS + ["site_id", "timestamp"])
    if require_targets:
        required.update(TARGET_COLUMNS)
    missing = required.difference(df.columns)
    if missing:
        issues.append(f"Missing columns: {sorted(missing)}")
    if df["timestamp"].isna().any():
        issues.append("Timestamp contains null values.")
    if df.duplicated(subset=["site_id", "timestamp"]).any():
        issues.append("Duplicate site_id/timestamp combinations found.")
    for site_id, frame in df.groupby("site_id"):
        if not frame["timestamp"].is_monotonic_increasing:
            issues.append(f"Site {site_id} is not sorted chronologically after preprocessing.")
    return ValidationReport(passed=not issues, issues=issues)

