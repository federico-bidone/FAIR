"""Covariance drift diagnostics."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def frobenius_relative_drift(sigma_t: NDArray[np.float64], sigma_tm1: NDArray[np.float64]) -> float:
    """Return the relative Frobenius norm drift between two covariance matrices."""

    if sigma_t.shape != sigma_tm1.shape:
        raise ValueError("Covariance matrices must share the same shape")
    num = np.linalg.norm(sigma_t - sigma_tm1, ord="fro")
    den = max(1e-12, np.linalg.norm(sigma_tm1, ord="fro"))
    return float(num / den)


def max_corr_drift(corr_t: NDArray[np.float64], corr_tm1: NDArray[np.float64]) -> float:
    """Compute the maximum absolute difference between correlation matrices."""

    if corr_t.shape != corr_tm1.shape:
        raise ValueError("Correlation matrices must share the same shape")
    diff = np.abs(corr_t - corr_tm1)
    return float(np.max(diff))


__all__ = ["frobenius_relative_drift", "max_corr_drift"]
