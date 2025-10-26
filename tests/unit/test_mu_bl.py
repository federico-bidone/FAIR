import numpy as np
import pandas as pd
import pytest

from fair3.engine.estimates import blend_mu, estimate_mu_ensemble, reverse_opt_mu_eq


def make_sample_frames(seed: int = 0) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2015-01-01", periods=60, freq=pd.offsets.MonthEnd())
    returns = pd.DataFrame(rng.normal(scale=0.02, size=(60, 3)), index=idx, columns=["A", "B", "C"])
    macro = pd.DataFrame(rng.normal(size=(60, 2)), index=idx, columns=["macro1", "macro2"])
    return returns, macro


def test_estimate_mu_ensemble_deterministic() -> None:
    returns, macro = make_sample_frames()
    mu_1 = estimate_mu_ensemble(returns, macro, cv_splits=4, seed=123)
    mu_2 = estimate_mu_ensemble(returns, macro, cv_splits=4, seed=123)
    pd.testing.assert_series_equal(mu_1, mu_2)
    assert mu_1.index.tolist() == ["A", "B", "C"]
    assert np.isfinite(mu_1.values).all()


def test_estimate_mu_ensemble_small_sample_fallback() -> None:
    returns, macro = make_sample_frames()
    small_returns = returns.iloc[:4, :1]
    small_macro = macro.iloc[:4]
    mu = estimate_mu_ensemble(small_returns, small_macro, cv_splits=3, seed=99)
    shrink_intensity = min(1.0, small_returns.shape[1] / small_returns.shape[0])
    expected = (1.0 - shrink_intensity) * small_returns.mean()
    pd.testing.assert_series_equal(mu, expected, check_names=False)


def test_reverse_opt_mu_eq_matches_manual() -> None:
    sigma = np.array([[0.04, 0.01], [0.01, 0.09]])
    w_mkt = np.array([0.6, 0.4])
    mu_eq = reverse_opt_mu_eq(sigma, w_mkt, vol_target=0.15)
    manual = 0.15 / np.sqrt(w_mkt @ sigma @ w_mkt) * (sigma @ w_mkt)
    np.testing.assert_allclose(mu_eq.to_numpy(), manual)


def test_blend_mu_fallback_and_blend() -> None:
    mu_eq = pd.Series([0.02, 0.01], index=["A", "B"])
    mu_star = pd.Series([0.03, 0.00], index=["A", "B"])
    fallback = blend_mu(mu_eq, mu_star, ir_view=0.1, tau_ir=0.15)
    assert fallback.omega == pytest.approx(1.0)
    pd.testing.assert_series_equal(fallback.mu_post, mu_eq)
    assert fallback.reason == "fallback"

    blend = blend_mu(mu_eq, mu_star, ir_view=0.2, tau_ir=0.15)
    assert blend.reason == "blend"
    assert blend.omega == pytest.approx(0.5)
    expected_post = 0.5 * mu_eq + 0.5 * mu_star
    pd.testing.assert_series_equal(blend.mu_post, expected_post)
