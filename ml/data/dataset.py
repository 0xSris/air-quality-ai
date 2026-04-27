from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


TRAIN_PATTERN = re.compile(r"site_(?P<site_id>\d+)_train_data\.csv")
UNSEEN_PATTERN = re.compile(r"site_(?P<site_id>\d+)_unseen_input_data\.csv")
FEATURE_COLUMNS = [
    "O3_forecast",
    "NO2_forecast",
    "T_forecast",
    "q_forecast",
    "u_forecast",
    "v_forecast",
    "w_forecast",
    "NO2_satellite",
    "HCHO_satellite",
    "ratio_satellite",
]
TARGET_COLUMNS = ["O3_target", "NO2_target"]
TEMPORAL_COLUMNS = ["year", "month", "day", "hour"]


@dataclass(slots=True)
class DatasetBundle:
    train: pd.DataFrame
    unseen: pd.DataFrame
    summary: dict


class DatasetLoader:
    def __init__(self, raw_dir: Path) -> None:
        self.raw_dir = raw_dir

    def load(self) -> DatasetBundle:
        train_frames = [self._load_csv(path, "train") for path in sorted(self.raw_dir.glob("site_*_train_data.csv"))]
        unseen_frames = [self._load_csv(path, "unseen") for path in sorted(self.raw_dir.glob("site_*_unseen_input_data.csv"))]
        coordinates = self._load_site_coordinates()
        train = self._finalize(pd.concat(train_frames, ignore_index=True), coordinates)
        unseen = self._finalize(pd.concat(unseen_frames, ignore_index=True), coordinates)
        summary = self._build_summary(train, unseen)
        return DatasetBundle(train=train, unseen=unseen, summary=summary)

    def _load_csv(self, path: Path, split: str) -> pd.DataFrame:
        match = TRAIN_PATTERN.match(path.name) or UNSEEN_PATTERN.match(path.name)
        if not match:
            raise ValueError(f"Unrecognized file naming convention: {path.name}")
        site_id = int(match.group("site_id"))
        df = pd.read_csv(path)
        df["site_id"] = site_id
        df["dataset_split"] = split
        for col in TEMPORAL_COLUMNS:
            df[col] = df[col].astype(int)
        df["timestamp"] = pd.to_datetime(df[["year", "month", "day", "hour"]])
        return df

    def _load_site_coordinates(self) -> pd.DataFrame:
        path = self.raw_dir / "lat_lon_sites.txt"
        coordinates = pd.read_csv(path, sep="\t")
        coordinates.columns = [column.strip() for column in coordinates.columns]
        return coordinates.rename(
            columns={"Site": "site_id", "Latitude N": "latitude", "Longitude E": "longitude"}
        )

    def _finalize(self, df: pd.DataFrame, coordinates: pd.DataFrame) -> pd.DataFrame:
        merged = df.merge(coordinates, on="site_id", how="left")
        merged = merged.sort_values(["site_id", "timestamp"]).reset_index(drop=True)
        return merged

    def _build_summary(self, train: pd.DataFrame, unseen: pd.DataFrame) -> dict:
        sites = []
        for site_id, frame in train.groupby("site_id"):
            unseen_rows = int((unseen["site_id"] == site_id).sum())
            sites.append(
                {
                    "site_id": int(site_id),
                    "latitude": float(frame["latitude"].iloc[0]),
                    "longitude": float(frame["longitude"].iloc[0]),
                    "train_rows": int(len(frame)),
                    "unseen_rows": unseen_rows,
                    "train_start": frame["timestamp"].min().isoformat(),
                    "train_end": frame["timestamp"].max().isoformat(),
                }
            )
        return {
            "total_sites": len(sites),
            "total_train_rows": int(len(train)),
            "total_unseen_rows": int(len(unseen)),
            "features": FEATURE_COLUMNS,
            "targets": TARGET_COLUMNS,
            "sites": sites,
        }

    @staticmethod
    def save_summary(path: Path, summary: dict) -> None:
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
