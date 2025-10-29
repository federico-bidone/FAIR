"""Hierarchical Risk Parity allocator."""

from __future__ import annotations

import numpy as np
import scipy.cluster.hierarchy as sch


def _corr_from_cov(Sigma: np.ndarray) -> np.ndarray:  # noqa: N803
    diag = np.sqrt(np.clip(np.diag(Sigma), 1e-12, None))
    outer = np.outer(diag, diag)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.divide(Sigma, outer, out=np.ones_like(Sigma), where=outer > 0)
    np.fill_diagonal(corr, 1.0)
    return corr


def _cluster_variance(cov: np.ndarray, indices: np.ndarray) -> float:
    sub = cov[np.ix_(indices, indices)]
    inv_diag = 1.0 / np.clip(np.diag(sub), 1e-12, None)
    weights = inv_diag / np.sum(inv_diag)
    return float(weights @ sub @ weights)


def _allocate(cov: np.ndarray, order: list[int]) -> np.ndarray:
    n = len(order)
    cov_ord = cov[np.ix_(order, order)]
    weights = np.ones(n)
    clusters = [np.arange(n)]
    while clusters:
        new_clusters: list[np.ndarray] = []
        for cluster in clusters:
            if cluster.size <= 1:
                continue
            split = cluster.size // 2
            left = cluster[:split]
            right = cluster[split:]
            var_left = _cluster_variance(cov_ord, left)
            var_right = _cluster_variance(cov_ord, right)
            denom = var_left + var_right
            alloc_left = 0.5 if denom <= 0 else var_right / denom
            alloc_right = 1.0 - alloc_left
            weights[left] *= alloc_left
            weights[right] *= alloc_right
            new_clusters.extend([left, right])
        clusters = new_clusters
    final = np.zeros(n)
    final[order] = weights
    s = float(np.sum(final))
    return final / s if s > 0 else np.full(n, 1.0 / n)


def generator_B_hrp(Sigma: np.ndarray) -> np.ndarray:  # noqa: N802,N803
    """Restituisce un'allocazione HRP per la covarianza ``Sigma``."""

    sigma = np.asarray(Sigma, dtype=float)
    n = sigma.shape[0]
    if n == 0:
        return np.array([])
    corr = _corr_from_cov(sigma)
    distance = np.sqrt(np.maximum(0.0, 0.5 * (1.0 - corr)))
    condensed = distance[np.triu_indices(n, k=1)]
    if condensed.size == 0:
        return np.full(n, 1.0 / n)
    link = sch.linkage(condensed, method="ward")
    order = sch.dendrogram(link, no_plot=True)["leaves"]
    return _allocate(sigma, order)
