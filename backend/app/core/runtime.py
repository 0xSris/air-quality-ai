from __future__ import annotations

from dataclasses import dataclass

from backend.app.core.config import Settings


@dataclass(slots=True)
class RuntimeStatus:
    ready: bool
    checks: dict[str, bool]


def validate_runtime(settings: Settings) -> RuntimeStatus:
    required_paths = {
        "processed_train": settings.processed_data_dir / "train_features.parquet",
        "processed_unseen": settings.processed_data_dir / "unseen_features.parquet",
        "dataset_summary": settings.processed_data_dir / "dataset_summary.json",
        "metadata": settings.artifacts_dir / "metadata.json",
    }
    checks = {name: path.exists() for name, path in required_paths.items()}
    return RuntimeStatus(ready=all(checks.values()), checks=checks)
