import numpy as np
import pytest

pytest.importorskip("hypothesis")

from hypothesis import given
from hypothesis import strategies as st

from fair3.engine.allocators import balance_clusters, erc_cluster_violation


@given(st.integers(min_value=2, max_value=5))
def test_balance_clusters_within_tol(k: int) -> None:
    rng = np.random.default_rng(42 + k)
    sigma = rng.normal(size=(k, k))
    sigma = sigma @ sigma.T + 0.1 * np.eye(k)
    w = rng.random(k)
    w /= w.sum()
    clusters = [list(range(0, k // 2)), list(range(k // 2, k))]
    tol = 0.05
    balanced = balance_clusters(w, sigma, clusters, tol)
    violation = erc_cluster_violation(balanced, sigma, clusters, tol)
    assert violation <= 1e-8
