from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.mapping import enforce_portfolio_te_budget, enforce_te_budget, tracking_error


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
    adjusted = enforce_portfolio_te_budget(weights, baseline, sigma, cap)
    new_te = tracking_error(adjusted, baseline, sigma)
    assert new_te <= cap + 1e-12
    np.testing.assert_allclose(adjusted.sum(), 1.0)


def test_enforce_te_budget_clamps_factor_exposures() -> None:
    exposures = np.array([0.3, -0.1, 0.05])
    target = np.array([0.1, -0.05, 0.0])
    series_exposures = pd.Series(exposures, index=["carry", "value", "momentum"])
    series_target = pd.Series(target, index=series_exposures.index)
    capped = enforce_te_budget(series_exposures, series_target, te_factor_max=0.1)
    diff = (capped - series_target).abs()
    assert (diff <= 0.1 + 1e-12).all()
