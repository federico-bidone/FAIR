"""Distributionally robust closed-form allocator."""

from __future__ import annotations

import numpy as np


def _regularised_inverse(Sigma: np.ndarray, rho: float) -> np.ndarray:  # noqa: N803
    sigma = 0.5 * (Sigma + Sigma.T)
    jitter = max(1e-6, rho)
    reg = sigma + jitter * np.eye(sigma.shape[0])
    return np.linalg.pinv(reg)


def generator_C_dro_closed(  # noqa: N802
    mu: np.ndarray,
    Sigma: np.ndarray,  # noqa: N803
    gamma: float,
    rho: float,  # noqa: N803
) -> np.ndarray:
    """Closed-form DRO solution with ridge regularisation."""

    mu = np.asarray(mu, dtype=float)
    sigma = np.asarray(Sigma, dtype=float)
    inv = _regularised_inverse(sigma, rho)
    raw = inv @ mu
    if np.allclose(raw, 0.0):
        return np.full_like(mu, 1.0 / mu.size)
    scaled = np.clip(raw / max(gamma, 1e-6), 0.0, None)
    total = float(np.sum(scaled))
    return scaled / total if total > 0 else np.full_like(mu, 1.0 / mu.size)
