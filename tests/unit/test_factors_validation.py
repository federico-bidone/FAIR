from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.factors.validation import (
    FactorValidationResult,
    cross_purged_splits,
    fdr_bh,
    validate_factor_set,
)


def _make_factors(n_days: int = 60, n_factors: int = 3) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2020-01-01", periods=n_days, freq="B")
    rng = np.random.default_rng(7)
    factors = pd.DataFrame(
        rng.normal(size=(n_days, n_factors)),
        index=dates,
        columns=[f"factor_{i}" for i in range(n_factors)],
    )
    assets = pd.DataFrame(
        rng.normal(size=(n_days, 4)),
        index=dates,
        columns=["asset_A", "asset_B", "asset_C", "asset_D"],
    )
    return factors, assets


def test_cross_purged_splits_embargo() -> None:
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    splits = cross_purged_splits(dates, n_splits=4, embargo=1)
    seen_tests: set[pd.Timestamp] = set()
    for train, test in splits:
        assert not set(train).intersection(set(test))
        seen_tests.update(test)
        for ts in test:
            assert ts not in train
            if ts - pd.Timedelta(days=1) in dates:
                assert ts - pd.Timedelta(days=1) not in train
            if ts + pd.Timedelta(days=1) in dates:
                assert ts + pd.Timedelta(days=1) not in train
    assert len(seen_tests) == len(dates)


def test_validate_factor_set_returns_results() -> None:
    factors, assets = _make_factors()
    results = validate_factor_set(factors, assets, n_splits=5, embargo=2, alpha=0.2, seed=21)
    assert len(results) == factors.shape[1]
    assert all(isinstance(item, FactorValidationResult) for item in results)
    for res in results:
        assert isinstance(res.sharpe, float)
        assert isinstance(res.dsr, float)
        assert isinstance(res.p_value, float)
        assert isinstance(res.ic_mean, float)
        assert isinstance(res.ic_std, float)


def test_fdr_bh_behaviour() -> None:
    pvals = [0.01, 0.04, 0.2, 0.5]
    mask = fdr_bh(pvals, alpha=0.1)
    assert mask.dtype == bool
    assert mask.sum() == 2
