from __future__ import annotations

import numpy as np
import pytest

try:
    from hypothesis import given
    from hypothesis import strategies as st
    from hypothesis.strategies import SearchStrategy
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.goals import GoalConfig, GoalParameters, simulate_goals


def _goal_strategy() -> SearchStrategy[GoalConfig]:
    return st.builds(
        GoalConfig,
        name=st.text(
            min_size=1,
            max_size=8,
            alphabet=st.characters(min_codepoint=97, max_codepoint=122),
        ),
        target=st.floats(
            min_value=10_000.0,
            max_value=300_000.0,
            allow_nan=False,
            allow_infinity=False,
        ),
        horizon_years=st.integers(min_value=1, max_value=30),
        p_min=st.floats(
            min_value=0.4,
            max_value=0.95,
            allow_nan=False,
            allow_infinity=False,
        ),
        weight=st.floats(
            min_value=0.1,
            max_value=2.0,
            allow_nan=False,
            allow_infinity=False,
        ),
    )


@given(
    goals=st.lists(_goal_strategy(), min_size=1, max_size=4),
    seed=st.integers(min_value=0, max_value=10_000),
)
def test_goal_probabilities_within_bounds(goals: list[GoalConfig], seed: int) -> None:
    parameters = GoalParameters.from_mapping(
        {
            "investor": "property",
            "contrib_monthly": 500.0,
            "initial_wealth": 10_000.0,
            "contribution_growth": 0.02,
        }
    )
    summary = simulate_goals(
        goals,
        draws=256,
        seed=seed,
        parameters=parameters,
    )
    probs = summary.results["probability"].to_numpy()
    assert np.all((probs >= 0.0) & (probs <= 1.0))
    if not np.isnan(summary.weighted_probability):
        assert 0.0 <= summary.weighted_probability <= 1.0
