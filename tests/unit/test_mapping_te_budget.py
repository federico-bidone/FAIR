from __future__ import annotations

import numpy as np

from fair3.engine.mapping import enforce_te_budget, tracking_error


def test_tracking_error_identity() -> None:
    sigma = np.eye(3)
    baseline = np.array([0.3, 0.4, 0.3])
    weights = np.array([0.2, 0.5, 0.3])
    te = tracking_error(weights, baseline, sigma)
    np.testing.assert_allclose(te, np.linalg.norm(weights - baseline))


def test_enforce_te_budget_shrinks_to_cap() -> None:
    sigma = np.eye(3)
    baseline = np.array([0.4, 0.3, 0.3])
    weights = np.array([0.8, 0.1, 0.1])
    cap = 0.1
    adjusted = enforce_te_budget(weights, baseline, sigma, cap)
    new_te = tracking_error(adjusted, baseline, sigma)
    assert new_te <= cap + 1e-12
    np.testing.assert_allclose(adjusted.sum(), 1.0)
