from pathlib import Path

from ml.data.dataset import DatasetLoader
from ml.data.validation import validate_dataframe


def test_dataset_loader_reads_expected_bundle():
    raw_dir = Path("ml/data/raw/Data_SIH_2025")
    bundle = DatasetLoader(raw_dir).load()

    assert bundle.summary["total_sites"] == 7
    assert {"O3_target", "NO2_target"}.issubset(bundle.train.columns)
    assert {"latitude", "longitude"}.issubset(bundle.train.columns)


def test_train_dataframe_validates():
    raw_dir = Path("ml/data/raw/Data_SIH_2025")
    bundle = DatasetLoader(raw_dir).load()
    report = validate_dataframe(bundle.train, require_targets=True)
    assert report.passed, report.issues

