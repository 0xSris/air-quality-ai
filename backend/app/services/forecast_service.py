from __future__ import annotations

from datetime import datetime

from backend.app.core.config import Settings
from backend.app.schemas.api import ForecastPoint, ForecastRequest, ForecastResponse
from backend.app.services.repository import DataRepository
from ml.inference.artifacts import ArtifactRegistry


class ForecastService:
    def __init__(self, repository: DataRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.registry = ArtifactRegistry(settings.artifacts_dir)

    def generate_forecast(self, request: ForecastRequest) -> ForecastResponse:
        model_name = request.model_name or self.settings.model_name
        horizon = request.horizon_hours or self.settings.forecast_horizon_hours
        model = self.registry.load_model(model_name, device=self.settings.model_device)
        unseen = self.repository.site_frame(request.site_id, split="unseen")
        model_feature_columns = self.repository.model_feature_columns(model_name)
        for column in model_feature_columns:
            if column not in unseen.columns:
                unseen[column] = 0.0
        future_inputs = unseen.tail(horizon).copy()
        if hasattr(model, "predict_next"):
            all_predictions = model.predict(unseen)
            aligned_predictions = all_predictions[-horizon:]
            residual_std = getattr(model, "residual_std", [5.0, 5.0])
            points = [
                ForecastPoint(
                    timestamp=row.timestamp.to_pydatetime(),
                    o3=float(pred[0]),
                    no2=float(pred[1]),
                    o3_lower=float(pred[0] - 1.96 * residual_std[0]),
                    o3_upper=float(pred[0] + 1.96 * residual_std[0]),
                    no2_lower=float(pred[1] - 1.96 * residual_std[1]),
                    no2_upper=float(pred[1] + 1.96 * residual_std[1]),
                )
                for row, pred in zip(future_inputs.itertuples(), aligned_predictions, strict=False)
            ]
            return ForecastResponse(
                site_id=request.site_id,
                horizon_hours=horizon,
                model_name=model_name,
                generated_at=datetime.utcnow(),
                points=points,
            )

        predictions = model.predict(future_inputs)
        residual = self.repository.metadata["metrics"][model_name]
        points = []
        for idx, row in enumerate(future_inputs.itertuples()):
            timestamp = row.timestamp.to_pydatetime()
            o3_pred, no2_pred = predictions[idx]
            o3_std = residual["O3_target"]["rmse"]
            no2_std = residual["NO2_target"]["rmse"]
            points.append(
                ForecastPoint(
                    timestamp=timestamp,
                    o3=float(o3_pred),
                    no2=float(no2_pred),
                    o3_lower=float(o3_pred - 1.96 * o3_std),
                    o3_upper=float(o3_pred + 1.96 * o3_std),
                    no2_lower=float(no2_pred - 1.96 * no2_std),
                    no2_upper=float(no2_pred + 1.96 * no2_std),
                )
            )
        return ForecastResponse(
            site_id=request.site_id,
            horizon_hours=horizon,
            model_name=model_name,
            generated_at=datetime.utcnow(),
            points=points,
        )
