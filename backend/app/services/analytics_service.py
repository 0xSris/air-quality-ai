from __future__ import annotations

import pandas as pd

from backend.app.schemas.api import DatasetSummaryResponse, PollutantPoint, TrendResponse
from backend.app.services.repository import DataRepository


class AnalyticsService:
    def __init__(self, repository: DataRepository) -> None:
        self.repository = repository

    def dataset_summary(self) -> DatasetSummaryResponse:
        return DatasetSummaryResponse.model_validate(self.repository.dataset_summary)

    def historical_trend(self, site_id: int, hours: int = 168) -> TrendResponse:
        frame = self.repository.observation_frame(site_id).tail(hours)
        points = [
            PollutantPoint(
                timestamp=row.timestamp.to_pydatetime(),
                o3=float(row.O3_target),
                no2=float(row.NO2_target),
                source="historical",
            )
            for row in frame.itertuples()
        ]
        return TrendResponse(site_id=site_id, points=points)

    def latest_context(self, site_id: int) -> pd.DataFrame:
        return self.repository.observation_frame(site_id)
