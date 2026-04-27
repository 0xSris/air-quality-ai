from __future__ import annotations

import pandas as pd


def temporal_split(df: pd.DataFrame, validation_fraction: float, test_fraction: float) -> dict[str, pd.DataFrame]:
    frames: dict[str, list[pd.DataFrame]] = {"train": [], "validation": [], "test": []}
    for _, site_frame in df.groupby("site_id"):
        n_rows = len(site_frame)
        test_start = int(n_rows * (1 - test_fraction))
        valid_start = int(n_rows * (1 - test_fraction - validation_fraction))
        frames["train"].append(site_frame.iloc[:valid_start])
        frames["validation"].append(site_frame.iloc[valid_start:test_start])
        frames["test"].append(site_frame.iloc[test_start:])
    return {key: pd.concat(value, ignore_index=True) for key, value in frames.items()}

