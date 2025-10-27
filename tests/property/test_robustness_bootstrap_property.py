from __future__ import annotations

import pytest

pytest.importorskip("hypothesis")

from hypothesis import given
from hypothesis import strategies as st

from fair3.engine.robustness import block_bootstrap_metrics


@given(
    st.lists(
        st.floats(min_value=-0.001, max_value=0.01, allow_nan=False),
        min_size=60,
        max_size=120,
    )
)
def test_bootstrap_exceedance_prob_under_threshold(samples: list[float]) -> None:
    metrics, gates = block_bootstrap_metrics(
        samples,
        block_size=10,
        draws=32,
        max_drawdown_threshold=-0.50,
        cagr_target=-0.5,
        seed=1234,
    )
    assert not metrics.empty
    assert {"sharpe", "cvar", "edar"}.issubset(metrics.columns)
    assert gates.exceedance_probability <= 0.05 + 1e-9
    assert gates.passes()
