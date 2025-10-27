from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


def tracking_error(weights: np.ndarray, baseline: np.ndarray, sigma: np.ndarray) -> float:
    """Compute the tracking error between two weight vectors.

    Args:
      weights: Candidate portfolio weights.
      baseline: Baseline or benchmark weights.
      sigma: Covariance matrix used for the tracking error metric.

    Returns:
      The non-negative tracking error value.

    Raises:
      ValueError: If the covariance matrix is not square or does not align with the
        weight vectors.
    """

    w = np.asarray(weights, dtype=float)
    b = np.asarray(baseline, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    if sigma.ndim != 2 or sigma.shape[0] != sigma.shape[1]:
        raise ValueError("sigma must be a square matrix")
    if w.shape != b.shape or w.shape[0] != sigma.shape[0]:
        raise ValueError("weights and baseline must match sigma dimensions")
    diff = w - b
    te2 = float(diff.T @ sigma @ diff)
    return float(np.sqrt(max(te2, 0.0)))


def enforce_portfolio_te_budget(
    weights: np.ndarray,
    baseline: np.ndarray,
    sigma: np.ndarray,
    cap: float,
) -> np.ndarray:
    """Shrink weights toward the baseline until the tracking error cap is met.

    Args:
      weights: Candidate weights before applying the tracking error budget.
      baseline: Baseline weights used as an anchor when shrinking exposures.
      sigma: Covariance matrix consistent with the weight vectors.
      cap: Maximum acceptable tracking error.

    Returns:
      Adjusted weights that satisfy the tracking error constraint and remain
      normalized if the baseline is normalized.

    Raises:
      ValueError: If the cap is negative or inputs are dimensionally
        inconsistent.
    """

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


def enforce_te_budget(
    exposures: pd.Series,
    target_exposure: pd.Series,
    te_factor_max: float,
    factors: Iterable[str] | None = None,
) -> pd.Series:
    """Clamp factor exposures within a per-factor tracking-error band.

    Args:
      exposures: Observed factor exposures derived from instrument betas.
      target_exposure: Target factor exposures from the optimized factor
        allocation.
      te_factor_max: Maximum absolute deviation tolerated per factor.
      factors: Optional subset of factor identifiers to evaluate; if omitted, all
        keys from ``target_exposure`` are considered.

    Returns:
      Adjusted factor exposures that deviate from the target by at most
      ``te_factor_max``.

    Raises:
      ValueError: If ``te_factor_max`` is negative.
    """

    if te_factor_max < 0:
        raise ValueError("te_factor_max must be non-negative")
    factors_list = list(factors) if factors is not None else list(target_exposure.index)
    aligned_target = target_exposure.reindex(factors_list).fillna(0.0)
    aligned_exposures = exposures.reindex(factors_list).fillna(0.0)
    if aligned_exposures.empty:
        return aligned_exposures
    diff = aligned_exposures - aligned_target
    if diff.abs().max() <= te_factor_max:
        return aligned_exposures
    clipped = aligned_target + diff.clip(lower=-te_factor_max, upper=te_factor_max)
    return clipped
