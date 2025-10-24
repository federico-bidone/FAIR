from __future__ import annotations

from collections import OrderedDict

import numpy as np
import scipy.cluster.hierarchy as sch


def _corr_from_cov(cov: np.ndarray) -> np.ndarray:
    diag = np.sqrt(np.clip(np.diag(cov), 1e-12, None))
    outer = np.outer(diag, diag)
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.divide(cov, outer, out=np.ones_like(cov), where=outer > 0)
    np.fill_diagonal(corr, 1.0)
    return corr


def _hrp_weights(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    if n == 0:
        return np.array([])
    if n == 1:
        return np.array([1.0])
    corr = _corr_from_cov(cov)
    distance = np.sqrt(np.maximum(0.0, 0.5 * (1.0 - corr)))
    condensed = distance[np.triu_indices(n, k=1)]
    if condensed.size == 0:
        return np.full(n, 1.0 / n)
    link = sch.linkage(condensed, method="ward")
    order = sch.dendrogram(link, no_plot=True)["leaves"]
    cov_ord = cov[np.ix_(order, order)]
    weights = np.ones(len(order))
    clusters = [np.arange(len(order))]
    while clusters:
        next_clusters: list[np.ndarray] = []
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
            next_clusters.extend([left, right])
        clusters = next_clusters
    final = np.zeros(n)
    final[order] = weights
    total = float(np.sum(final))
    return final / total if total > 0 else np.full(n, 1.0 / n)


def _cluster_variance(cov: np.ndarray, indices: np.ndarray) -> float:
    sub = cov[np.ix_(indices, indices)]
    inv_diag = 1.0 / np.clip(np.diag(sub), 1e-12, None)
    w = inv_diag / np.sum(inv_diag)
    return float(w @ sub @ w)


def hrp_weights(Sigma: np.ndarray, labels: list[str]) -> np.ndarray:  # noqa: N802,N803
    """Return intra-cluster HRP weights with equal factor budgets."""

    sigma = np.asarray(Sigma, dtype=float)
    n = sigma.shape[0]
    if n == 0:
        return np.array([])
    if sigma.shape[0] != sigma.shape[1]:
        raise ValueError("Sigma must be square")
    if len(labels) != n:
        raise ValueError("labels length must match Sigma dimension")

    label_order = OrderedDict.fromkeys(labels)
    cluster_weights = np.zeros(n, dtype=float)
    n_clusters = len(label_order)
    if n_clusters == 0:
        return np.zeros(n, dtype=float)

    for label in label_order:
        members = [i for i, lab in enumerate(labels) if lab == label]
        sub = sigma[np.ix_(members, members)]
        intra = _hrp_weights(sub)
        budget = 1.0 / n_clusters
        cluster_weights[members] = budget * intra

    total = float(cluster_weights.sum())
    return cluster_weights / total if total > 0 else np.full(n, 1.0 / n)
