from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from backend.app.core.config import get_settings

PROFILE_ARTIFACTS_ROOT = Path("ml/profiles/artifacts")
PROFILE_PROCESSED_ROOT = Path("ml/profiles/processed")


def replace_tree(source: Path, target: Path) -> None:
    items_to_copy = [(child, child.is_dir()) for child in source.iterdir()]
    target.mkdir(parents=True, exist_ok=True)
    for child in target.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    for child, is_dir in items_to_copy:
        destination = target / child.name
        if is_dir:
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(child, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=["zip_only", "external_augmented"])
    args = parser.parse_args()

    settings = get_settings()
    artifacts_source = PROFILE_ARTIFACTS_ROOT / args.profile
    processed_source = PROFILE_PROCESSED_ROOT / args.profile

    if not artifacts_source.exists():
        raise FileNotFoundError(f"Missing artifacts profile: {artifacts_source}")
    if not processed_source.exists():
        raise FileNotFoundError(f"Missing processed-data profile: {processed_source}")

    replace_tree(artifacts_source, settings.artifacts_dir)
    replace_tree(processed_source, settings.processed_data_dir)
    print(f"Activated profile: {args.profile}")


if __name__ == "__main__":
    main()
