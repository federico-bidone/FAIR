from __future__ import annotations

import numpy as np

from fair3.engine.mapping import hrp_weights


def test_hrp_weights_cluster_budgets() -> None:
    sigma = np.diag([0.04, 0.09, 0.01, 0.02])
    labels = ["growth", "growth", "defensive", "defensive"]
    weights = hrp_weights(sigma, labels)
    np.testing.assert_allclose(weights.sum(), 1.0)
    np.testing.assert_allclose(weights[:2].sum(), 0.5, atol=1e-6)
    np.testing.assert_allclose(weights[2:].sum(), 0.5, atol=1e-6)
    # Within each cluster HRP favours lower variance names
    assert weights[0] > weights[1]
    assert weights[2] > weights[3]


def test_hrp_weights_single_member_cluster() -> None:
    sigma = np.diag([0.02, 0.03, 0.04])
    labels = ["core", "satellite", "satellite"]
    weights = hrp_weights(sigma, labels)
    np.testing.assert_allclose(weights.sum(), 1.0)
    np.testing.assert_allclose(weights[labels.index("core")], 1 / 2)
    np.testing.assert_allclose(weights[1:].sum(), 1 / 2)
