from __future__ import annotations

import numpy as np
import pytest

try:
    from hypothesis import given
    from hypothesis import strategies as st
    from hypothesis.strategies import SearchStrategy
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.mapping import clip_trades_to_adv, max_trade_notional


def _case_strategy() -> SearchStrategy[tuple[np.ndarray, np.ndarray, np.ndarray, float, float]]:
    def build_case(
        n: int,
    ) -> SearchStrategy[tuple[np.ndarray, np.ndarray, np.ndarray, float, float]]:
        return st.tuples(
            st.lists(
                st.floats(min_value=-0.5, max_value=0.5, allow_nan=False),
                min_size=n,
                max_size=n,
            ).map(np.array),
            st.lists(
                st.floats(min_value=1.0, max_value=10_000.0, allow_nan=False),
                min_size=n,
                max_size=n,
            ).map(np.array),
            st.lists(
                st.floats(min_value=1.0, max_value=1_000.0, allow_nan=False),
                min_size=n,
                max_size=n,
            ).map(np.array),
            st.floats(min_value=10_000.0, max_value=1_000_000.0, allow_nan=False),
            st.floats(min_value=0.0, max_value=0.1, allow_nan=False),
        )

    return st.integers(min_value=1, max_value=5).flatmap(build_case)


@given(_case_strategy())
def test_clip_trades_respects_adv_caps(
    case: tuple[np.ndarray, np.ndarray, np.ndarray, float, float],
) -> None:
    delta_w, adv, prices, portfolio_value, cap_ratio = case
    adjusted = clip_trades_to_adv(delta_w, portfolio_value, adv, prices, cap_ratio)
    caps = max_trade_notional(adv, prices, cap_ratio)
    trade_value = np.abs(adjusted) * portfolio_value
    assert np.all(trade_value <= caps + 1e-8)
