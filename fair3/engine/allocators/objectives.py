"""Objectives used by allocation generators."""

from __future__ import annotations

import numpy as np


def sharpe_objective(w: np.ndarray, mu: np.ndarray, Sigma: np.ndarray) -> float:  # noqa: N803
    """Return the portfolio Sharpe ratio for ``w``.

    The routine is deterministic and guards against numerical underflow when the
    variance term is nearly zero.
    """

    w = np.asarray(w, dtype=float)
    mu = np.asarray(mu, dtype=float)
    sigma = np.asarray(Sigma, dtype=float)
    numerator = float(w @ mu)
    variance = float(w @ (sigma @ w))
    if variance <= 1e-16:
        return 0.0
    return numerator / float(np.sqrt(variance))


def dro_penalty(w: np.ndarray, rho: float) -> float:
    """Simple 2-norm penalty used as Wasserstein DRO regulariser."""

    w = np.asarray(w, dtype=float)
    rho = float(max(0.0, rho))
    return rho * float(np.linalg.norm(w, ord=2))
