"""Constraint diagnostics for allocation engines."""

from __future__ import annotations

import numpy as np

from .erc import risk_contributions


def erc_cluster_violation(
    w: np.ndarray,
    Sigma: np.ndarray,  # noqa: N803
    clusters: list[list[int]],
    tol: float,  # noqa: N803
) -> float:
    """Return the ERC cluster deviation minus tolerance.

    Negative values indicate the deviation is within the acceptable tolerance
    band. The helper works with ragged cluster definitions and ignores empty
    clusters gracefully.
    """

    if not clusters:
        return -tol

    rc = risk_contributions(np.asarray(w, dtype=float), np.asarray(Sigma, dtype=float))
    totals = []
    for idx in clusters:
        if not idx:
            continue
        idx_arr = np.asarray(idx, dtype=int)
        totals.append(float(np.sum(rc[idx_arr])))
    if not totals:
        return -tol
    target = float(np.mean(totals))
    deviation = max(abs(t - target) for t in totals)
    return deviation - float(tol)
