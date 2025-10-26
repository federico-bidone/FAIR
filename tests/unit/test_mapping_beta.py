from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.mapping import beta_ci_bootstrap, cap_weights_by_beta_ci, rolling_beta_ridge


def _toy_data(n_obs: int = 12) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    idx = pd.date_range("2020-01-01", periods=n_obs, freq=pd.offsets.MonthEnd())
    rng = np.random.default_rng(123)
    factors = pd.DataFrame(rng.normal(size=(n_obs, 2)), index=idx, columns=["carry", "value"])
    beta = np.array([[0.4, -0.2, 0.1], [0.3, 0.1, -0.4]])
    returns = pd.DataFrame(factors.to_numpy() @ beta, index=idx, columns=["ETF1", "ETF2", "ETF3"])
    return returns, factors, beta


def test_rolling_beta_ridge_recovers_coefficients() -> None:
    returns, factors, beta = _toy_data()
    betas = rolling_beta_ridge(returns, factors, window=6, lambda_beta=1e-8)
    last_row = betas.dropna().iloc[-1]
    expected = beta.T.reshape(-1)
    np.testing.assert_allclose(last_row.to_numpy(), expected, atol=1e-6)


def test_rolling_beta_respects_sign_constraints() -> None:
    returns, factors, _ = _toy_data()
    betas = rolling_beta_ridge(
        returns,
        factors,
        window=6,
        lambda_beta=0.0,
        sign_prior={"carry": 1},
        enforce_sign=True,
    )
    carry_slice = betas.xs("carry", axis=1, level="factor")
    assert (carry_slice.dropna() >= -1e-12).all().all()


def test_beta_ci_bootstrap_shapes_and_bounds() -> None:
    returns, factors, _ = _toy_data()
    betas = rolling_beta_ridge(returns, factors, window=5, lambda_beta=0.01)
    ci = beta_ci_bootstrap(returns, factors, betas, B=128, alpha=0.2)
    non_na = ci.dropna().iloc[-1]
    lower = non_na.xs("lower", level="bound")
    upper = non_na.xs("upper", level="bound")
    assert lower.shape == upper.shape
    assert (lower <= upper).all().all()


def test_cap_weights_by_beta_ci_scales_uncertain_instruments() -> None:
    weights = pd.Series([0.6, 0.4], index=["ETF1", "ETF2"], name="weight")
    columns = pd.MultiIndex.from_product(
        [["ETF1", "ETF2"], ["carry"], ["lower", "upper"]],
        names=["instrument", "factor", "bound"],
    )
    data = np.array(
        [
            [0.1, 0.6, 0.2, 0.3],
            [0.1, 0.2, 0.15, 0.25],
        ]
    )
    idx = pd.date_range("2021-01-31", periods=2, freq=pd.offsets.MonthEnd())
    ci = pd.DataFrame(data, index=idx, columns=columns)
    capped = cap_weights_by_beta_ci(weights, ci, tau_beta=0.3)
    assert capped.sum().round(10) == 1.0
    assert capped.loc["ETF1"] < weights.loc["ETF1"]
    assert capped.loc["ETF2"] > weights.loc["ETF2"]
