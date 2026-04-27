import json
from pathlib import Path
import shutil

import pandas as pd
from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_summary_endpoint_with_stubbed_files(monkeypatch):
    tmp_path = Path("tmp/test-api-smoke")
    if tmp_path.exists():
        shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    processed_dir = tmp_path / "processed"
    artifacts_dir = tmp_path / "artifacts"
    processed_dir.mkdir()
    artifacts_dir.mkdir()

    train = pd.DataFrame(
        {
            "site_id": [1],
            "timestamp": ["2024-01-01T00:00:00"],
            "latitude": [28.6],
            "longitude": [77.1],
            "O3_target": [10.0],
            "NO2_target": [20.0],
        }
    )
    unseen = pd.DataFrame(
        {
            "site_id": [1],
            "timestamp": ["2024-01-02T00:00:00"],
            "latitude": [28.6],
            "longitude": [77.1],
            "O3_forecast": [12.0],
            "NO2_forecast": [21.0],
        }
    )
    train.to_parquet(processed_dir / "train_features.parquet", index=False)
    unseen.to_parquet(processed_dir / "unseen_features.parquet", index=False)
    (processed_dir / "dataset_summary.json").write_text(
        json.dumps(
            {
                "total_sites": 1,
                "total_train_rows": 1,
                "total_unseen_rows": 1,
                "features": ["O3_forecast", "NO2_forecast"],
                "targets": ["O3_target", "NO2_target"],
                "sites": [
                    {
                        "site_id": 1,
                        "latitude": 28.6,
                        "longitude": 77.1,
                        "train_rows": 1,
                        "unseen_rows": 1,
                        "train_start": "2024-01-01T00:00:00",
                        "train_end": "2024-01-01T00:00:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (artifacts_dir / "metadata.json").write_text(
        json.dumps(
            {
                "active_model": "baseline_random_forest",
                "available_models": ["baseline_random_forest"],
                "metrics": {"baseline_random_forest": {"O3_target": {"rmse": 1.0}, "NO2_target": {"rmse": 1.0}}},
                "feature_columns": ["O3_forecast", "NO2_forecast"],
                "targets": ["O3_target", "NO2_target"],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PROCESSED_DATA_DIR", str(processed_dir))
    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("TMP", str(tmp_path / "tmp"))
    monkeypatch.setenv("TEMP", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir(exist_ok=True)

    from backend.app.core.config import get_settings

    get_settings.cache_clear()
    client = TestClient(app)
    response = client.get("/data/summary")

    assert response.status_code == 200
    assert response.json()["total_sites"] == 1
    shutil.rmtree(tmp_path, ignore_errors=True)
