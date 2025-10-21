from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair3.engine.etl.cleaning import (
    HampelConfig,
    apply_hampel,
    clean_price_history,
    prepare_estimation_copy,
    winsorize_series,
)


def test_apply_hampel_removes_spike() -> None:
    series = pd.Series([100.0, 101.0, 250.0, 102.0, 103.0])
    config = HampelConfig(window=3, n_sigma=3.0)
    cleaned = apply_hampel(series, config)
    expected = np.median([101.0, 250.0, 102.0])
    assert cleaned.iloc[2] != pytest.approx(series.iloc[2])
    assert cleaned.iloc[2] == pytest.approx(expected)


def test_winsorize_series_bounds() -> None:
    rng = np.random.default_rng(0)
    series = pd.Series(rng.normal(size=1000))
    wins = winsorize_series(series, lower=0.05, upper=0.95)
    lower_bound, upper_bound = series.quantile([0.05, 0.95])
    assert wins.min() >= lower_bound - 1e-9
    assert wins.max() <= upper_bound + 1e-9


def test_clean_price_history_applies_per_symbol() -> None:
    frame = pd.DataFrame(
        {
            "symbol": ["A", "A", "A", "A", "B", "B"],
            "price": [1.0, 1.01, 10_000.0, 1.02, 2.0, 2.5],
        }
    )
    cleaned = clean_price_history(frame)
    assert cleaned.loc[2, "price"] != frame.loc[2, "price"]
    assert cleaned.loc[0, "price"] == frame.loc[0, "price"]


def test_prepare_estimation_copy_winsorizes() -> None:
    series = pd.Series([-10.0, -1.0, 0.0, 1.0, 10.0])
    wins = prepare_estimation_copy(series, winsor_quantiles=(0.2, 0.8))
    assert wins.iloc[0] == pytest.approx(series.quantile(0.2))
    assert wins.iloc[-1] == pytest.approx(series.quantile(0.8))
