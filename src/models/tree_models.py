"""
Regularized Residual Draft Alpha Models (CatBoost / LightGBM).
Fits draft alpha strictly as a regularized residual regressor: target = y - P_baseline.
"""
import joblib
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from src.models.base_model import BaseDraftModel
import logging

logger = logging.getLogger(__name__)

class ResidualDraftModel(BaseDraftModel):
    """
    Explicit Residual Draft Alpha Model.
    P_final = clip(P_baseline + Delta_draft, 0.03, 0.97)
    """
    def __init__(
        self,
        iterations: int = 400,
        learning_rate: float = 0.02,
        depth: int = 4,
        l2_leaf_reg: float = 10.0,
        random_seed: int = 42
    ):
        self.iterations = iterations
        self.learning_rate = learning_rate
        self.depth = depth
        self.l2_leaf_reg = l2_leaf_reg
        self.random_seed = random_seed
        self.model = CatBoostRegressor(
            iterations=self.iterations,
            learning_rate=self.learning_rate,
            depth=self.depth,
            l2_leaf_reg=self.l2_leaf_reg,
            random_seed=self.random_seed,
            verbose=False
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: np.ndarray,
        base_probs: np.ndarray,
        val_X: pd.DataFrame = None,
        val_y: np.ndarray = None,
        val_base_probs: np.ndarray = None
    ):
        logger.info("Fitting Regularized Residual Draft Alpha Model (y - P_baseline)...")
        train_residuals = y - np.clip(base_probs, 0.03, 0.97)
        
        eval_set = None
        if val_X is not None and val_y is not None and val_base_probs is not None:
            val_residuals = val_y - np.clip(val_base_probs, 0.03, 0.97)
            eval_set = (val_X, val_residuals)
            
        self.model.fit(
            X,
            train_residuals,
            eval_set=eval_set,
            early_stopping_rounds=40,
            verbose=False
        )
        return self

    def predict_proba(self, X: pd.DataFrame, base_probs: np.ndarray) -> np.ndarray:
        """
        Predicts calibrated probability: P_final = clip(P_baseline + Delta_draft, 0.03, 0.97).
        """
        draft_delta = np.clip(self.model.predict(X), -0.08, 0.08)
        base_p = np.clip(base_probs, 0.03, 0.97)
        return np.clip(base_p + draft_delta, 0.03, 0.97)

    def save(self, filepath: str):
        joblib.dump(self.model, filepath)

    def load(self, filepath: str):
        self.model = joblib.load(filepath)
