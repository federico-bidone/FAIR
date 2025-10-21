from __future__ import annotations

import numpy as np


def tracking_error(weights: np.ndarray, baseline: np.ndarray, sigma: np.ndarray) -> float:
    """Compute tracking error between ``weights`` and ``baseline``."""

    w = np.asarray(weights, dtype=float)
    b = np.asarray(baseline, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    if sigma.shape[0] != sigma.shape[1]:
        raise ValueError("Sigma must be square")
    if w.shape != b.shape or w.shape[0] != sigma.shape[0]:
        raise ValueError("weights and baseline must match Sigma dimension")
    diff = w - b
    te2 = float(diff.T @ sigma @ diff)
    return float(np.sqrt(max(te2, 0.0)))


def enforce_te_budget(
    weights: np.ndarray,
    baseline: np.ndarray,
    sigma: np.ndarray,
    cap: float,
) -> np.ndarray:
    """Shrink weights toward ``baseline`` until tracking error ≤ ``cap``."""

    if cap < 0:
        raise ValueError("cap must be non-negative")
    te = tracking_error(weights, baseline, sigma)
    if te <= cap or te == 0:
        return np.asarray(weights, dtype=float)
    scale = cap / te
    adjusted = baseline + scale * (np.asarray(weights, dtype=float) - baseline)
    total = float(np.sum(adjusted))
    if total != 0:
        adjusted = adjusted / total
    return adjusted
