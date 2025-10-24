from __future__ import annotations

import pandas as pd
import pytest

from fair3.engine.regime import apply_hysteresis, tilt_lambda


def test_apply_hysteresis_enforces_dwell_and_cooldown() -> None:
    idx = pd.date_range("2020-01-01", periods=8, freq="B")
    probs = pd.Series([0.2, 0.7, 0.8, 0.5, 0.3, 0.6, 0.7, 0.2], index=idx)

    state = apply_hysteresis(probs, on=0.6, off=0.4, dwell_days=2, cooldown_days=2)

    expected = pd.Series([0, 1, 1, 1, 0, 0, 0, 0], index=idx, dtype=float)

    assert state.equals(expected)


def test_apply_hysteresis_threshold_validation() -> None:
    idx = pd.date_range("2020-01-01", periods=3, freq="B")
    probs = pd.Series([0.1, 0.2, 0.3], index=idx)

    with pytest.raises(ValueError):
        apply_hysteresis(probs, on=0.3, off=0.4, dwell_days=1, cooldown_days=0)

    with pytest.raises(ValueError):
        apply_hysteresis(probs, on=0.6, off=0.4, dwell_days=-1, cooldown_days=0)


def test_tilt_lambda_clamps_range() -> None:
    assert tilt_lambda(0.55) == 0.0
    assert tilt_lambda(0.95) == 1.0
    assert tilt_lambda(0.15) == 0.0
    assert 0.0 < tilt_lambda(0.65) < 1.0
