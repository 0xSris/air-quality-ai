import argparse
from pathlib import Path

from backend.app.core.config import get_settings
from ml.training.pipeline import TrainingPipeline


PROFILE_ARTIFACTS_ROOT = Path("ml/profiles/artifacts")
PROFILE_PROCESSED_ROOT = Path("ml/profiles/processed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-external-features", action="store_true")
    parser.add_argument("--refresh-external-cache", action="store_true")
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()
    settings = get_settings()
    if args.profile:
        artifacts_dir = PROFILE_ARTIFACTS_ROOT / args.profile
        processed_dir = PROFILE_PROCESSED_ROOT / args.profile
    else:
        artifacts_dir = settings.artifacts_dir
        processed_dir = settings.processed_data_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    pipeline = TrainingPipeline(
        raw_data_dir=settings.raw_data_dir,
        processed_dir=processed_dir,
        artifacts_dir=artifacts_dir,
        config_path=Path("ml/configs/default.yaml"),
        settings=settings,
        device=settings.model_device,
    )
    metadata = pipeline.run(
        use_external_features=args.use_external_features or settings.enable_external_training_augmentation,
        refresh_external=args.refresh_external_cache,
    )
    print("Training complete.")
    print(metadata["metrics"])


if __name__ == "__main__":
    main()
