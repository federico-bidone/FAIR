from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.goals import (
    GoalConfig,
    load_goal_configs_from_yaml,
    run_goal_monte_carlo,
    simulate_goals,
)


def test_load_goal_configs_from_yaml() -> None:
    goals = load_goal_configs_from_yaml("configs/goals.yml")
    assert [goal.name for goal in goals] == ["pensione", "casa"]
    assert all(goal.horizon_years > 0 for goal in goals)


def test_simulate_goals_is_deterministic() -> None:
    goals = [
        GoalConfig(name="test", target=50_000.0, horizon_years=5, p_min=0.7, weight=1.0),
        GoalConfig(name="bonus", target=100_000.0, horizon_years=8, p_min=0.6, weight=0.5),
    ]
    summary_a = simulate_goals(
        goals,
        draws=1024,
        seed=123,
        monthly_contribution=600.0,
        initial_wealth=10_000.0,
        contribution_growth=0.015,
    )
    summary_b = simulate_goals(
        goals,
        draws=1024,
        seed=123,
        monthly_contribution=600.0,
        initial_wealth=10_000.0,
        contribution_growth=0.015,
    )
    pd.testing.assert_frame_equal(summary_a.results, summary_b.results)
    np.testing.assert_allclose(summary_a.weighted_probability, summary_b.weighted_probability)
    assert np.all(np.diff(summary_a.glidepath["growth"]) <= 1e-9)
    assert np.allclose(summary_a.glidepath.sum(axis=1), 1.0)


def test_run_goal_monte_carlo_writes_artifacts(tmp_path: Path) -> None:
    goals = load_goal_configs_from_yaml("configs/goals.yml")
    summary, artifacts = run_goal_monte_carlo(
        goals,
        draws=512,
        seed=7,
        monthly_contribution=500.0,
        initial_wealth=5_000.0,
        contribution_growth=0.02,
        output_dir=tmp_path,
    )
    assert summary.draws == 512
    assert artifacts.summary_csv.exists()
    assert artifacts.report_pdf.exists()
    exported = pd.read_csv(artifacts.summary_csv)
    assert {"goal", "probability", "passes"}.issubset(exported.columns)
