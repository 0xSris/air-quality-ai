from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ForecasterModel(ABC):
    name: str

    @abstractmethod
    def fit(self, train_frame: pd.DataFrame, validation_frame: pd.DataFrame) -> None:
        raise NotImplementedError

    @abstractmethod
    def predict(self, frame: pd.DataFrame):
        raise NotImplementedError

    @abstractmethod
    def save(self, output_dir) -> None:
        raise NotImplementedError

