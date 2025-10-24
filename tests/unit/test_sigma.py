import numpy as np
import pandas as pd
import pytest

from fair3.engine.estimates import (
    ewma_regime,
    factor_shrink,
    frobenius_relative_drift,
    graphical_lasso_bic,
    ledoit_wolf,
    max_corr_drift,
    median_of_covariances,
)


@pytest.fixture()
def sample_returns() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    data = rng.normal(size=(120, 4))
    index = pd.date_range("2020-01-01", periods=120, freq="B")
    return pd.DataFrame(data, index=index, columns=[f"asset_{i}" for i in range(4)])


def test_ledoit_wolf_positive_semidefinite(sample_returns: pd.DataFrame) -> None:
    cov = ledoit_wolf(sample_returns)
    eigs = np.linalg.eigvalsh(cov)
    assert eigs.min() >= -1e-10


def test_graphical_lasso_bic_selects_candidate(sample_returns: pd.DataFrame) -> None:
    cov = graphical_lasso_bic(sample_returns, lambdas=[0.01, 0.05])
    assert cov.shape == (sample_returns.shape[1],) * 2
    eigs = np.linalg.eigvalsh(cov)
    assert eigs.min() >= -1e-10


def test_factor_shrink_structure(sample_returns: pd.DataFrame) -> None:
    cov = factor_shrink(sample_returns, n_factors=2)
    assert cov.shape == (sample_returns.shape[1],) * 2
    eigs = np.linalg.eigvalsh(cov)
    assert eigs.min() >= -1e-10


def test_median_of_covariances_requires_inputs() -> None:
    with pytest.raises(ValueError):
        median_of_covariances([])


def test_median_of_covariances_returns_psd(sample_returns: pd.DataFrame) -> None:
    covs = [
        ledoit_wolf(sample_returns.iloc[:60]),
        factor_shrink(sample_returns.iloc[60:]),
    ]
    cov = median_of_covariances(covs)
    eigs = np.linalg.eigvalsh(cov)
    assert eigs.min() >= -1e-10


def test_ewma_regime_convex_combination(sample_returns: pd.DataFrame) -> None:
    cov1 = ledoit_wolf(sample_returns.iloc[:80])
    cov2 = factor_shrink(sample_returns.iloc[40:])
    ewma = ewma_regime(cov1, cov2, lambda_r=0.6)
    assert ewma.shape == cov1.shape
    eigs = np.linalg.eigvalsh(ewma)
    assert eigs.min() >= -1e-10


def test_frobenius_relative_drift_zero_when_equal(sample_returns: pd.DataFrame) -> None:
    cov = ledoit_wolf(sample_returns)
    assert frobenius_relative_drift(cov, cov) == pytest.approx(0.0)


def test_max_corr_drift_matches_manual() -> None:
    corr_old = np.array([[1.0, 0.5], [0.5, 1.0]])
    corr_new = np.array([[1.0, 0.2], [0.2, 1.0]])
    assert max_corr_drift(corr_old, corr_new) == pytest.approx(0.3)
