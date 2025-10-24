"""Equal risk contribution helpers."""

from __future__ import annotations

import numpy as np


def risk_contributions(w: np.ndarray, Sigma: np.ndarray) -> np.ndarray:  # noqa: N803
    r"""Return marginal contribution of each asset to portfolio risk.

    The calculation follows the standard ERC definition ``RC_i = w_i (\Sigma w)_i``
    with a small epsilon in the denominator to guard against division by zero.
    """

    w = np.asarray(w, dtype=float)
    sigma = np.asarray(Sigma, dtype=float)
    m = sigma @ w
    total = float(w.T @ m) + 1e-16
    return (w * m) / total


def _cluster_totals(rc: np.ndarray, clusters: list[list[int]]) -> list[float]:
    totals: list[float] = []
    for idx in clusters:
        if not idx:
            totals.append(0.0)
            continue
        rc_sum = float(np.sum(rc[np.asarray(idx, dtype=int)]))
        totals.append(rc_sum)
    return totals


def balance_clusters(
    w: np.ndarray,
    Sigma: np.ndarray,  # noqa: N803
    clusters: list[list[int]],
    tol: float,
    max_iter: int = 50,
) -> np.ndarray:
    """Scale cluster weights so their risk contributions align within ``tol``.

    The routine rescales weights iteratively until the absolute deviation of
    cluster-level risk contributions from their mean falls below ``tol`` or the
    iteration budget is exhausted.
    """

    if not clusters:
        return w
    sigma = np.asarray(Sigma, dtype=float)
    w_adj = np.maximum(np.asarray(w, dtype=float), 0.0)

    for _ in range(max_iter):
        rc = risk_contributions(w_adj, sigma)
        totals = _cluster_totals(rc, clusters)
        target = float(np.mean(totals)) if totals else 0.0
        if target == 0.0:
            break
        deviations = [abs(t - target) for t in totals]
        if deviations and max(deviations) <= tol:
            break
        for idx, total in zip(clusters, totals, strict=False):
            if not idx or total == 0.0:
                continue
            scale = target / total
            w_adj[np.asarray(idx, dtype=int)] *= scale
        s = float(np.sum(w_adj))
        if s > 0:
            w_adj /= s

    return w_adj
