"""Hysteresis and tilt utilities for the regime overlay."""

from __future__ import annotations

import pandas as pd


def apply_hysteresis(
    p: pd.Series,
    on: float,
    off: float,
    dwell_days: int,
    cooldown_days: int,
    activate_streak: int = 1,
    deactivate_streak: int = 1,
) -> pd.Series:
    """Convert crisis probabilities into a binary regime state with hysteresis."""

    if on <= off:
        msg = "`on` threshold must exceed `off` threshold."
        raise ValueError(msg)
    if dwell_days < 0 or cooldown_days < 0:
        msg = "`dwell_days` and `cooldown_days` must be non-negative."
        raise ValueError(msg)
    if activate_streak < 1 or deactivate_streak < 1:
        msg = "Activation and deactivation streaks must be at least one observation."
        raise ValueError(msg)

    if p.empty:
        return pd.Series(dtype=float)

    p = p.sort_index().astype(float).clip(0.0, 1.0).fillna(0.0)
    state = []
    in_crisis = False
    days_in_state = 0
    cooldown = 0
    activate_counter = 0
    deactivate_counter = 0

    for _, value in p.items():
        if in_crisis:
            days_in_state += 1
            if value <= off:
                deactivate_counter += 1
            else:
                deactivate_counter = 0
            if deactivate_counter >= deactivate_streak and days_in_state >= dwell_days:
                in_crisis = False
                days_in_state = 0
                cooldown = cooldown_days
                deactivate_counter = 0
        else:
            if cooldown > 0:
                cooldown -= 1
                activate_counter = 0
            else:
                if value >= on:
                    activate_counter += 1
                else:
                    activate_counter = 0
                if activate_counter >= activate_streak:
                    in_crisis = True
                    days_in_state = 0
                    activate_counter = 0
                    deactivate_counter = 0
        state.append(1.0 if in_crisis else 0.0)

    return pd.Series(state, index=p.index)


def tilt_lambda(p_t: float) -> float:
    """Map crisis probability to a tilt weight within [0, 1]."""

    x = (float(p_t) - 0.55) / 0.2
    return max(0.0, min(1.0, x))


__all__ = [
    "apply_hysteresis",
    "tilt_lambda",
]
