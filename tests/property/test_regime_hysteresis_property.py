from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

try:
    from hypothesis import given
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.regime import apply_hysteresis


@given(st.lists(st.floats(min_value=0.0, max_value=1.0), min_size=5, max_size=60))
def test_hysteresis_cooldown_blocks_reentry(probabilities: list[float]) -> None:
    idx = pd.date_range("2020-01-01", periods=len(probabilities), freq="B")
    series = pd.Series(probabilities, index=idx)

    state = apply_hysteresis(
        series,
        on=0.6,
        off=0.4,
        dwell_days=2,
        cooldown_days=3,
        activate_streak=2,
        deactivate_streak=2,
    )
    values = state.to_numpy()

    assert set(np.unique(values)).issubset({0.0, 1.0})

    for i in range(1, len(values)):
        if values[i - 1] == 1.0 and values[i] == 0.0:
            for step in range(1, 4):
                if i + step < len(values):
                    assert values[i + step] == 0.0
