from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair3.engine.regime import CommitteeWeights, crisis_probability


def test_crisis_probability_range_and_alignment() -> None:
    idx = pd.date_range("2020-01-01", periods=12, freq="B")
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
            "pmi": np.linspace(52.0, 48.0, len(idx)),
            "infl": np.linspace(2.0, 3.0, len(idx)),
        },
        index=idx,
    )

    prob = crisis_probability(returns, vol, macro)

    assert list(prob.index) == list(idx)
    assert ((prob >= 0.0) & (prob <= 1.0)).all()
    assert prob.nunique() > 1


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
