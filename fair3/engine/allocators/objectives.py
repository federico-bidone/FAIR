"""Obiettivi utilizzati dai generatori di allocazione."""

from __future__ import annotations

import numpy as np


def sharpe_objective(w: np.ndarray, mu: np.ndarray, Sigma: np.ndarray) -> float:  # noqa: N803
    """Restituisce lo Sharpe ratio di portafoglio per ``w``.

    La routine è deterministica e protegge dal sottoscorimento numerico quando il
    termine di varianza è quasi nullo.
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
    """Penalità 2-norma semplice usata come regolarizzatore Wasserstein DRO."""

    w = np.asarray(w, dtype=float)
    rho = float(max(0.0, rho))
    return rho * float(np.linalg.norm(w, ord=2))
