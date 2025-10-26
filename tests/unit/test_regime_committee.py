from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair3.engine.regime import CommitteeWeights, crisis_probability, regime_probability


def _build_panel(idx: pd.DatetimeIndex) -> pd.DataFrame:
    returns = pd.DataFrame(
        {
            "asset_a": np.linspace(-0.02, 0.02, len(idx)),
            "asset_b": np.linspace(0.015, -0.015, len(idx)),
        },
        index=idx,
    )
    vol = pd.Series(np.linspace(0.1, 0.3, len(idx)), index=idx)
    macro = pd.DataFrame(
        {
            "inflation_yoy": np.linspace(1.8, 2.4, len(idx)),
            "pmi": np.linspace(52.0, 48.0, len(idx)),
            "real_rate": np.linspace(-0.01, 0.01, len(idx)),
        },
        index=idx,
    )
    return pd.concat(
        {
            "returns": returns,
            "volatility": vol.to_frame(name="vol"),
            "macro": macro,
        },
        axis=1,
    )


def test_regime_probability_generates_expected_columns() -> None:
    idx = pd.date_range("2020-01-01", periods=60, freq="B")
    panel = _build_panel(idx)

    scores = regime_probability(panel, {"regime": {}}, seed=7)

    expected_cols = {
        "p_crisis",
        "p_hmm",
        "p_volatility",
        "p_macro",
        "hmm_state",
        "vol_state",
        "macro_trigger",
        "regime_flag",
    }
    assert expected_cols.issubset(set(scores.columns))
    assert scores.index.equals(idx)
    assert ((scores["p_crisis"] >= 0.0) & (scores["p_crisis"] <= 1.0)).all()
    assert scores["regime_flag"].isin({0.0, 1.0}).all()


def test_committee_weights_normalise_and_validate() -> None:
    weights = CommitteeWeights(hmm=0.6, volatility=0.2, macro=0.2)
    normalised = weights.normalised()
    assert pytest.approx(sum(normalised)) == 1.0

    with pytest.raises(ValueError):
        CommitteeWeights(0.0, 0.0, 0.0).normalised()


def test_crisis_probability_empty_intersection_returns_empty() -> None:
    idx_returns = pd.date_range("2020-01-01", periods=5, freq="B")
    idx_vol = pd.date_range("2020-02-01", periods=5, freq="B")
    returns = pd.DataFrame({"asset": np.linspace(-0.01, 0.01, len(idx_returns))}, index=idx_returns)
    vol = pd.Series(np.linspace(0.1, 0.2, len(idx_vol)), index=idx_vol)
    macro = pd.DataFrame({"pmi": np.linspace(50.0, 49.0, len(idx_returns))}, index=idx_returns)

    prob = crisis_probability(returns, vol, macro)
    assert prob.empty


def test_regime_macro_signal_influences_probability() -> None:
    idx = pd.date_range("2021-01-01", periods=40, freq="B")
    base_panel = _build_panel(idx)
    stressed_macro = base_panel.copy()
    stressed_macro["macro", "pmi"] = 45.0
    stressed_macro["macro", "inflation_yoy"] = 3.0
    stressed_macro["macro", "real_rate"] = 0.02

    neutral = regime_probability(base_panel, {"regime": {}}, seed=11)
    stressed = regime_probability(stressed_macro, {"regime": {}}, seed=11)

    assert stressed["p_crisis"].iloc[-1] > neutral["p_crisis"].iloc[-1]
