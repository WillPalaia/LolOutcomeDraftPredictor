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
        sample_weight: np.ndarray = None,
        val_X: pd.DataFrame = None,
        val_y: np.ndarray = None,
        val_base_probs: np.ndarray = None
    ):
        logger.info("Fitting Regularized Residual Draft Alpha Model (y - P_baseline)...")
        train_residuals = y - np.clip(base_probs, 0.03, 0.97)
        
        # If sample_weight not explicitly passed and patch_num is in features, compute heavy patch weights
        if sample_weight is None and isinstance(X, pd.DataFrame) and 'patch_num' in X.columns:
            max_p = X['patch_num'].max()
            patch_deltas = (max_p - X['patch_num']).clip(lower=0)
            sample_weight = np.exp(-0.06 * patch_deltas) * (1.0 + 3.0 * (X['patch_num'] == max_p).astype(float))
            sample_weight = sample_weight / sample_weight.mean()
            logger.info("Applied heavy patch recency sample weighting (4x multiplier on current patch games).")
            
        eval_set = None
        if val_X is not None and val_y is not None and val_base_probs is not None:
            val_residuals = val_y - np.clip(val_base_probs, 0.03, 0.97)
            eval_set = (val_X, val_residuals)
            
        self.model.fit(
            X,
            train_residuals,
            sample_weight=sample_weight,
            eval_set=eval_set,
            early_stopping_rounds=40,
            verbose=False
        )
        return self

    def get_feature_importances(self, feature_names: list = None) -> pd.DataFrame:
        """Returns sorted parameter weights/importances for each feature."""
        raw_imp = self.model.get_feature_importance()
        names = feature_names if feature_names else [f"feature_{i}" for i in range(len(raw_imp))]
        df_imp = pd.DataFrame({'feature': names, 'importance': raw_imp}).sort_values('importance', ascending=False)
        return df_imp

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

