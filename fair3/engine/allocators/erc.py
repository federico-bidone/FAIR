"""Utility per l'analisi dei contributi di rischio egualizzati."""

from __future__ import annotations

import numpy as np


def risk_contributions(w: np.ndarray, Sigma: np.ndarray) -> np.ndarray:  # noqa: N803
    r"""Restituisce il contributo marginale di ogni asset al rischio di portafoglio.

    Il calcolo segue la definizione ERC standard ``RC_i = w_i (\Sigma w)_i`` con un
    piccolo epsilon nel denominatore per proteggere dalle divisioni per zero.
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
    """Ribilancia i pesi dei cluster così che i contributi di rischio siano entro ``tol``.

    La routine ridimensiona i pesi in modo iterativo finché la deviazione assoluta
    dei contributi di rischio a livello di cluster rispetto alla media scende sotto
    ``tol`` o finché non si esaurisce il budget di iterazioni.
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
