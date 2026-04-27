import numpy as np

from ml.evaluation.metrics import regression_metrics


def test_regression_metrics_returns_expected_targets():
    y_true = np.array([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]])
    y_pred = np.array([[1.1, 1.9], [1.9, 3.1], [3.2, 4.2]])

    metrics = regression_metrics(y_true, y_pred, ["O3_target", "NO2_target"])

    assert set(metrics.keys()) == {"O3_target", "NO2_target"}
    assert metrics["O3_target"]["rmse"] > 0
    assert metrics["NO2_target"]["mae"] > 0

