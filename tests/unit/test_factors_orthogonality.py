from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.factors.orthogonality import (
    OrthogonalizationResult,
    condition_number,
    enforce_orthogonality,
    merge_correlated_factors,
)


def _make_correlated_factors(rows: int = 40) -> pd.DataFrame:
    dates = pd.date_range("2021-01-01", periods=rows, freq="B")
    rng = np.random.default_rng(11)
    base = rng.normal(size=rows)
    data = np.vstack(
        [
            base,
            base * 0.9 + rng.normal(scale=0.1, size=rows),
            rng.normal(size=rows),
        ]
    ).T
    return pd.DataFrame(data, index=dates, columns=["f1", "f2", "f3"])


def test_merge_correlated_factors_reduces_columns() -> None:
    factors = _make_correlated_factors()
    merged, mapping = merge_correlated_factors(factors, threshold=0.8)
    assert merged.shape[1] <= factors.shape[1]
    assert set().union(*mapping.values()).issubset(set(factors.columns))


def test_enforce_orthogonality_caps_condition_number() -> None:
    factors = _make_correlated_factors()
    orig = condition_number(factors)
    result = enforce_orthogonality(factors, corr_threshold=0.8, cond_threshold=10)
    assert isinstance(result, OrthogonalizationResult)
    assert result.condition_number <= orig + 1e-6
    assert result.factors.index.equals(factors.index)
