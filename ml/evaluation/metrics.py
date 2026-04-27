from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


def refined_index_of_agreement(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    numerator = np.sum(np.abs(y_pred - y_true))
    denominator = 2 * np.sum(np.abs(y_true - np.mean(y_true)))
    if denominator == 0:
        return 1.0
    ratio = numerator / denominator
    return float(1 - ratio) if ratio <= 1 else float(1 / ratio - 1)


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray, targets: list[str]) -> dict:
    metrics: dict[str, dict[str, float]] = {}
    for idx, target in enumerate(targets):
        truth = y_true[:, idx]
        pred = y_pred[:, idx]
        metrics[target] = {
            "rmse": float(np.sqrt(mean_squared_error(truth, pred))),
            "mae": float(mean_absolute_error(truth, pred)),
            "r2": float(r2_score(truth, pred)),
            "ria": refined_index_of_agreement(truth, pred),
        }
    return metrics

