from __future__ import annotations

import numpy as np
import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.execution import drift_bands_exceeded, should_trade


@settings(max_examples=25, deadline=None)
@given(
    st.integers(min_value=2, max_value=10),
    st.floats(min_value=0.01, max_value=0.05),
)
def test_no_trade_when_drift_within_band(dim: int, band: float) -> None:
    w_old = np.full(dim, 1.0 / dim)
    delta = np.linspace(-band * 0.25, band * 0.25, dim)
    w_new = w_old + delta
    rc_old = w_old.copy()
    rc_new = w_new.copy()

    drift_ok = drift_bands_exceeded(w_old, w_new, rc_old, rc_new, band)
    decision = should_trade(drift_ok, eb_lb=0.05, cost=0.0, tax=0.0, turnover_ok=True)

    assert not drift_ok
    assert decision is False
