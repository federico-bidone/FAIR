"""Execution decision helper rules."""

from __future__ import annotations

import numpy as np


def drift_bands_exceeded(
    w_old: np.ndarray,
    w_new: np.ndarray,
    rc_old: np.ndarray,
    rc_new: np.ndarray,
    band: float,
) -> bool:
    """Return ``True`` when weight or risk contribution drift exceeds ``band``."""

    w_old = np.asarray(w_old, dtype=float)
    w_new = np.asarray(w_new, dtype=float)
    rc_old = np.asarray(rc_old, dtype=float)
    rc_new = np.asarray(rc_new, dtype=float)

    shapes = {w_old.shape, w_new.shape, rc_old.shape, rc_new.shape}
    if len(shapes) != 1:
        raise ValueError("Input arrays must share the same shape")
    if band < 0:
        raise ValueError("band must be non-negative")

    weight_drift = float(np.max(np.abs(w_new - w_old)))
    rc_drift = float(np.max(np.abs(rc_new - rc_old)))
    return (weight_drift > band) or (rc_drift > band)


def expected_benefit(
    delta_w: np.ndarray,
    mu_instr: np.ndarray,
    sigma_instr: np.ndarray,
    w_old: np.ndarray,
    w_new: np.ndarray,
) -> float:
    """Compute a lower-bound expected benefit from trading."""

    delta_w = np.asarray(delta_w, dtype=float)
    mu_instr = np.asarray(mu_instr, dtype=float)
    sigma_instr = np.asarray(sigma_instr, dtype=float)
    w_old = np.asarray(w_old, dtype=float)
    w_new = np.asarray(w_new, dtype=float)

    if mu_instr.ndim != 1 or w_old.ndim != 1 or w_new.ndim != 1 or delta_w.ndim != 1:
        raise ValueError("All vector inputs must be one-dimensional")
    if mu_instr.shape != w_old.shape or w_old.shape != w_new.shape or delta_w.shape != w_old.shape:
        raise ValueError("All vector inputs must share the same shape")
    if sigma_instr.shape != (w_old.size, w_old.size):
        raise ValueError("sigma_instr must be square with dimension matching weights")

    if not np.allclose(delta_w, w_new - w_old):
        raise ValueError("delta_w must equal w_new - w_old")

    mu_old = float(w_old @ mu_instr)
    mu_new = float(w_new @ mu_instr)
    var_old = float(w_old @ sigma_instr @ w_old)
    var_new = float(w_new @ sigma_instr @ w_new)
    variance_change = var_new - var_old

    return (mu_new - mu_old) - 0.5 * variance_change
