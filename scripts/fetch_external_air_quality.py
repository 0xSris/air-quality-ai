from __future__ import annotations

import argparse
from datetime import date

import pandas as pd

from backend.app.core.config import get_settings
from ml.data.dataset import DatasetLoader
from ml.data.external_sources import OpenMeteoAirQualityClient, OpenMeteoConfig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    args = parser.parse_args()

    settings = get_settings()
    client = OpenMeteoAirQualityClient(
        OpenMeteoConfig(
            timezone=settings.live_external_timezone,
            domains=settings.live_external_domains,
            timeout_seconds=settings.live_external_timeout_seconds,
        )
    )
    bundle = DatasetLoader(settings.raw_data_dir).load()
    combined = pd.concat([bundle.train, bundle.unseen], ignore_index=True, sort=False)
    output_dir = settings.external_data_dir / "openmeteo"
    output_dir.mkdir(parents=True, exist_ok=True)

    for site_id, frame in combined.groupby("site_id"):
        dataset_start = frame["timestamp"].min().date()
        if settings.live_external_domains == "cams_global":
            dataset_start = max(dataset_start, date(2022, 8, 1))
        start_date = args.start_date or dataset_start.isoformat()
        end_date = args.end_date or frame["timestamp"].max().date().isoformat()
        external = client.fetch_range(
            latitude=float(frame["latitude"].iloc[0]),
            longitude=float(frame["longitude"].iloc[0]),
            start_date=start_date,
            end_date=end_date,
            site_id=int(site_id),
        )
        cache_path = output_dir / f"site_{site_id}_history.parquet"
        external.to_parquet(cache_path, index=False)
        print(f"Saved {len(external)} rows to {cache_path}")


if __name__ == "__main__":
    main()
