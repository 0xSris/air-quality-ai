from __future__ import annotations

from datetime import date

import pandas as pd

from backend.app.core.config import Settings
from ml.data.external_sources import OpenMeteoAirQualityClient, OpenMeteoConfig


class ExternalFeatureAugmentor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenMeteoAirQualityClient(
            OpenMeteoConfig(
                timezone=settings.live_external_timezone,
                domains=settings.live_external_domains,
                timeout_seconds=settings.live_external_timeout_seconds,
            )
        )

    def augment(
        self,
        train: pd.DataFrame,
        unseen: pd.DataFrame,
        *,
        refresh: bool = False,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        combined = pd.concat([train, unseen], ignore_index=True, sort=False)
        external_frames: list[pd.DataFrame] = []
        for site_id, frame in combined.groupby("site_id"):
            cache_path = self.settings.external_data_dir / "openmeteo" / f"site_{site_id}_history.parquet"
            external_frame = None if refresh else self.client.load_cached_frame(cache_path)
            if external_frame is None:
                start_date = frame["timestamp"].min().date()
                if self.settings.live_external_domains == "cams_global":
                    start_date = max(start_date, date(2022, 8, 1))
                external_frame = self.client.fetch_range(
                    latitude=float(frame["latitude"].iloc[0]),
                    longitude=float(frame["longitude"].iloc[0]),
                    start_date=start_date.isoformat(),
                    end_date=frame["timestamp"].max().date().isoformat(),
                    site_id=int(site_id),
                )
                self.client.cache_frame(external_frame, cache_path)
            external_frames.append(external_frame)
        if external_frames:
            external_all = pd.concat(external_frames, ignore_index=True)
            combined = combined.merge(external_all, on=["site_id", "timestamp"], how="left")
        return (
            combined.loc[combined["dataset_split"] == "train"].reset_index(drop=True),
            combined.loc[combined["dataset_split"] == "unseen"].reset_index(drop=True),
        )
