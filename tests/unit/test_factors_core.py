from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.factors.core import FactorLibrary, compute_macro_factors


def _synthetic_panel(rows: int = 60, symbols: int = 8) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("2020-01-01", periods=rows, freq="B")
    tickers = [f"ETF{i}" for i in range(symbols)]
    idx = pd.MultiIndex.from_product([dates, tickers], names=["date", "symbol"])
    rng = np.random.default_rng(123)
    ret_values = rng.normal(0.0005, 0.01, size=len(idx))
    returns = pd.DataFrame({"ret": ret_values}, index=idx)

    panel = returns.copy()
    by_symbol = panel.groupby(level="symbol")["ret"]
    panel["lag_ma_5"] = by_symbol.transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    panel["lag_ma_21"] = by_symbol.transform(lambda s: s.shift(1).rolling(21, min_periods=1).mean())
    panel["lag_vol_21"] = by_symbol.transform(
        lambda s: s.shift(1).rolling(21, min_periods=1).std()
    ).fillna(0.005)
    features = panel[["lag_ma_5", "lag_ma_21", "lag_vol_21"]]
    return returns, features


def test_factor_library_shapes_and_metadata() -> None:
    returns, features = _synthetic_panel()
    factors, definitions = compute_macro_factors(returns, features)

    expected_columns = [
        "global_mkt",
        "global_momentum",
        "short_term_reversal",
        "value_rebound",
        "carry_roll_down",
        "quality_low_vol",
        "defensive_stability",
        "liquidity_risk",
        "growth_cycle",
        "inflation_hedge",
        "rates_beta",
    ]

    assert list(factors.columns) == expected_columns
    assert len(definitions) == len(expected_columns)
    assert all(defn.expected_sign in (-1, 1) for defn in definitions)
    assert factors.index.equals(returns.index.get_level_values(0).unique())
    assert (factors.loc[:, "inflation_hedge"] == 0).all()
    assert (factors.loc[:, "rates_beta"] == 0).all()


def test_macro_overlay_uses_input_series() -> None:
    returns, features = _synthetic_panel()
    dates = returns.index.get_level_values(0).unique()
    macro = pd.DataFrame(
        {
            "inflation": np.linspace(100, 110, len(dates)),
            "policy_rate": np.linspace(1.0, 0.5, len(dates)),
        },
        index=dates,
    )
    factors, _ = compute_macro_factors(returns, features, macro=macro)
    inflation_diff = macro["inflation"].diff().fillna(0.0)
    rates_diff = -macro["policy_rate"].diff().fillna(0.0)
    pd.testing.assert_series_equal(
        factors["inflation_hedge"], inflation_diff, check_names=False, check_freq=False
    )
    pd.testing.assert_series_equal(
        factors["rates_beta"], rates_diff, check_names=False, check_freq=False
    )


def test_factor_library_quantile_requires_features() -> None:
    returns, features = _synthetic_panel()
    features = features.drop(columns=["lag_ma_5"])
    try:
        FactorLibrary(returns, features)
        raise AssertionError("FactorLibrary should require lag_ma_5 column")
    except KeyError as exc:  # noqa: PERF203 - explicit assertion
        assert "lag_ma_5" in str(exc)
