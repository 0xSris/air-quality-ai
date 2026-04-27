from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ml.data.dataset import TARGET_COLUMNS
from ml.training.base import ForecasterModel


class LSTMRegressor(nn.Module):
    def __init__(self, input_size: int, hidden_size: int, num_layers: int, dropout: float, output_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
            batch_first=True,
        )
        self.head = nn.Sequential(nn.Linear(hidden_size, hidden_size), nn.ReLU(), nn.Linear(hidden_size, output_size))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        outputs, _ = self.lstm(x)
        return self.head(outputs[:, -1, :])


@dataclass(slots=True)
class SequenceArtifacts:
    feature_imputer: SimpleImputer
    feature_scaler: StandardScaler
    target_scaler: StandardScaler


class LSTMForecaster(ForecasterModel):
    name = "lstm"

    def __init__(self, feature_columns: list[str], lookback_hours: int, config: dict, device: str = "cpu") -> None:
        self.feature_columns = feature_columns
        self.lookback_hours = lookback_hours
        self.device = torch.device(device)
        self.config = config
        self.model = LSTMRegressor(
            input_size=len(feature_columns),
            hidden_size=config.get("hidden_size", 64),
            num_layers=config.get("num_layers", 2),
            dropout=config.get("dropout", 0.2),
            output_size=len(TARGET_COLUMNS),
        ).to(self.device)
        self.artifacts = SequenceArtifacts(
            feature_imputer=SimpleImputer(strategy="median"),
            feature_scaler=StandardScaler(),
            target_scaler=StandardScaler(),
        )
        self.residual_std = np.array([1.0, 1.0], dtype=float)

    def _make_sequences(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        sequences = []
        targets = []
        for _, site_frame in frame.groupby("site_id"):
            x_raw = site_frame[self.feature_columns].to_numpy(dtype=float)
            y_raw = site_frame[TARGET_COLUMNS].to_numpy(dtype=float)
            for idx in range(self.lookback_hours, len(site_frame)):
                sequences.append(x_raw[idx - self.lookback_hours : idx])
                targets.append(y_raw[idx])
        return np.asarray(sequences), np.asarray(targets)

    def fit(self, train_frame: pd.DataFrame, validation_frame: pd.DataFrame) -> None:
        x_train, y_train = self._make_sequences(train_frame)
        x_valid, y_valid = self._make_sequences(validation_frame)
        n_samples, window, n_features = x_train.shape
        x_train = x_train.reshape(-1, n_features)
        x_valid = x_valid.reshape(-1, n_features)
        x_train = self.artifacts.feature_imputer.fit_transform(x_train)
        x_valid = self.artifacts.feature_imputer.transform(x_valid)
        x_train = self.artifacts.feature_scaler.fit_transform(x_train).reshape(n_samples, window, n_features)
        x_valid = self.artifacts.feature_scaler.transform(x_valid).reshape(x_valid.shape[0] // window, window, n_features)
        y_train_scaled = self.artifacts.target_scaler.fit_transform(y_train)
        y_valid_scaled = self.artifacts.target_scaler.transform(y_valid)

        train_loader = DataLoader(
            TensorDataset(torch.tensor(x_train, dtype=torch.float32), torch.tensor(y_train_scaled, dtype=torch.float32)),
            batch_size=self.config.get("batch_size", 128),
            shuffle=True,
        )
        valid_x = torch.tensor(x_valid, dtype=torch.float32, device=self.device)
        valid_y = torch.tensor(y_valid_scaled, dtype=torch.float32, device=self.device)
        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.config.get("learning_rate", 1e-3),
            weight_decay=self.config.get("weight_decay", 1e-4),
        )
        loss_fn = nn.MSELoss()
        best_loss = float("inf")
        best_state = None
        epochs = self.config.get("epochs", 12)

        for _ in range(epochs):
            self.model.train()
            for batch_x, batch_y in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                optimizer.zero_grad()
                loss = loss_fn(self.model(batch_x), batch_y)
                loss.backward()
                optimizer.step()
            self.model.eval()
            with torch.no_grad():
                valid_pred = self.model(valid_x)
                valid_loss = loss_fn(valid_pred, valid_y).item()
            if valid_loss < best_loss:
                best_loss = valid_loss
                best_state = self.model.state_dict()

        if best_state is not None:
            self.model.load_state_dict(best_state)
        with torch.no_grad():
            preds = self.model(valid_x).cpu().numpy()
        preds_unscaled = self.artifacts.target_scaler.inverse_transform(preds)
        self.residual_std = np.std(y_valid - preds_unscaled, axis=0)

    def predict(self, frame: pd.DataFrame):
        x_seq, _ = self._make_sequences(frame.assign(O3_target=0.0, NO2_target=0.0))
        if len(x_seq) == 0:
            return np.empty((0, 2))
        n_samples, window, n_features = x_seq.shape
        flat = x_seq.reshape(-1, n_features)
        flat = self.artifacts.feature_imputer.transform(flat)
        flat = self.artifacts.feature_scaler.transform(flat).reshape(n_samples, window, n_features)
        with torch.no_grad():
            preds = self.model(torch.tensor(flat, dtype=torch.float32, device=self.device)).cpu().numpy()
        return self.artifacts.target_scaler.inverse_transform(preds)

    def predict_next(self, history_frame: pd.DataFrame) -> np.ndarray:
        sequence = history_frame[self.feature_columns].tail(self.lookback_hours).to_numpy(dtype=float)
        sequence = self.artifacts.feature_imputer.transform(sequence)
        sequence = self.artifacts.feature_scaler.transform(sequence)
        tensor = torch.tensor(sequence[None, :, :], dtype=torch.float32, device=self.device)
        with torch.no_grad():
            pred = self.model(tensor).cpu().numpy()
        return self.artifacts.target_scaler.inverse_transform(pred)[0]

    def save(self, output_dir: Path) -> None:
        torch.save(
            {
                "state_dict": self.model.state_dict(),
                "feature_columns": self.feature_columns,
                "lookback_hours": self.lookback_hours,
                "config": self.config,
                "residual_std": self.residual_std.tolist(),
                "feature_imputer": self.artifacts.feature_imputer,
                "feature_scaler": self.artifacts.feature_scaler,
                "target_scaler": self.artifacts.target_scaler,
            },
            output_dir / f"{self.name}.pt",
        )

