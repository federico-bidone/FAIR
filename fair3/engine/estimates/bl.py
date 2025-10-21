from __future__ import annotations

import numpy as np
import pandas as pd

from .mu import MuBlend

__all__ = ["reverse_opt_mu_eq", "blend_mu"]


def reverse_opt_mu_eq(
    sigma: np.ndarray,
    w_mkt: np.ndarray | pd.Series,
    vol_target: float,
) -> pd.Series:
    if sigma.ndim != 2 or sigma.shape[0] != sigma.shape[1]:
        raise ValueError("Sigma must be a square matrix")
    if np.any(~np.isfinite(sigma)):
        raise ValueError("Sigma must contain finite values")

    if isinstance(w_mkt, pd.Series):
        weights = w_mkt.to_numpy(dtype=float, copy=True)
        index = w_mkt.index
    else:
        weights = np.asarray(w_mkt, dtype=float)
        if weights.ndim != 1 or weights.shape[0] != sigma.shape[0]:
            raise ValueError("w_mkt length must match Sigma dimensions")
        index = pd.Index(range(sigma.shape[0]), name="asset")

    s2 = float(weights.T @ sigma @ weights)
    if s2 <= 0:
        return pd.Series(np.zeros_like(weights), index=index)
    delta = vol_target / np.sqrt(s2) if vol_target > 0 else 0.0
    mu_eq = delta * (sigma @ weights)
    return pd.Series(mu_eq, index=index)


def blend_mu(
    mu_eq: pd.Series,
    mu_star: pd.Series,
    ir_view: float,
    tau_ir: float,
) -> MuBlend:
    mu_eq = mu_eq.astype(float)
    mu_star = mu_star.astype(float).reindex(mu_eq.index).fillna(0.0)
    if ir_view < tau_ir:
        return MuBlend(mu_post=mu_eq, mu_star=mu_star, mu_eq=mu_eq, omega=1.0, reason="fallback")

    omega = 0.5
    mu_post = omega * mu_eq + (1.0 - omega) * mu_star
    return MuBlend(mu_post=mu_post, mu_star=mu_star, mu_eq=mu_eq, omega=omega, reason="blend")
