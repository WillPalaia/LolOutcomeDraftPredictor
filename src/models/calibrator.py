"""
Probability Calibration and Brier Score Optimization.
Ensures predicted win probabilities reflect genuine underlying event frequencies.
"""
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

class ProbabilityCalibrator:
    """
    Fits Platt scaling (Logistic) or Isotonic Regression on out-of-fold predictions.
    """
    def __init__(self, method: str = "isotonic"):
        self.method = method
        if method == "isotonic":
            self.calibrator = IsotonicRegression(out_of_bounds="clip")
        else:
            self.calibrator = LogisticRegression()

    def fit(self, raw_probs: np.ndarray, y_true: np.ndarray):
        raw_probs = np.clip(raw_probs, 1e-6, 1 - 1e-6)
        if self.method == "isotonic":
            self.calibrator.fit(raw_probs, y_true)
        else:
            logits = np.log(raw_probs / (1.0 - raw_probs)).reshape(-1, 1)
            self.calibrator.fit(logits, y_true)
        return self

    def calibrate(self, raw_probs: np.ndarray) -> np.ndarray:
        raw_probs = np.clip(raw_probs, 1e-6, 1 - 1e-6)
        if self.method == "isotonic":
            return np.clip(self.calibrator.predict(raw_probs), 0.01, 0.99)
        else:
            logits = np.log(raw_probs / (1.0 - raw_probs)).reshape(-1, 1)
            return self.calibrator.predict_proba(logits)[:, 1]

def calculate_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """
    Expected Calibration Error (ECE).
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    total_samples = len(y_true)
    
    for i in range(n_bins):
        bin_mask = (y_prob >= bin_edges[i]) & (y_prob < bin_edges[i + 1])
        if np.sum(bin_mask) > 0:
            bin_acc = np.mean(y_true[bin_mask])
            bin_conf = np.mean(y_prob[bin_mask])
            bin_size = np.sum(bin_mask)
            ece += (bin_size / total_samples) * np.abs(bin_acc - bin_conf)
            
    return float(ece)
