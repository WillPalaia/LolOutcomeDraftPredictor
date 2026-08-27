"""
Abstract Base Model Interface.
"""
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd

class BaseDraftModel(ABC):
    @abstractmethod
    def fit(self, X: pd.DataFrame, y: np.ndarray, val_X: pd.DataFrame = None, val_y: np.ndarray = None):
        pass

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return 1D array of Blue win probabilities."""
        pass

    @abstractmethod
    def save(self, filepath: str):
        pass

    @abstractmethod
    def load(self, filepath: str):
        pass
