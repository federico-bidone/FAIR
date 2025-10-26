"""Unit tests for the goals Monte Carlo engine."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.goals import (
    GoalConfig,
    GoalParameters,
    GoalSimulationSummary,
    RegimeCurves,
    goal_monte_carlo,
    load_goal_configs_from_yaml,
    load_goal_parameters,
    run_goal_monte_carlo,
    simulate_goals,
)


def _sample_parameters() -> GoalParameters:
    """Return representative goal parameters for testing."""

    return GoalParameters.from_mapping(
        {
            "investor": "test_family",
            "contrib_monthly": 600.0,
            "contribution_growth": 0.015,
            "initial_wealth": 10_000.0,
            "contribution_plan": [
                {"start_year": 0, "end_year": 5, "amount": 100.0, "frequency": "monthly"},
                {"start_year": 10, "end_year": 12, "amount": 2_500.0, "frequency": "lump_sum"},
            ],
            "withdrawals": [{"year": 15, "amount": 5_000.0}],
        }
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
    parameters = _sample_parameters()
    summary_a = simulate_goals(goals, draws=1024, seed=123, parameters=parameters)
    summary_b = simulate_goals(goals, draws=1024, seed=123, parameters=parameters)
    pd.testing.assert_frame_equal(summary_a.results, summary_b.results)
    np.testing.assert_allclose(summary_a.weighted_probability, summary_b.weighted_probability)
    for name in summary_a.glidepaths:
        pd.testing.assert_frame_equal(summary_a.glidepaths[name], summary_b.glidepaths[name])
    for name in summary_a.fan_charts:
        pd.testing.assert_frame_equal(summary_a.fan_charts[name], summary_b.fan_charts[name])


def test_glidepath_adjusts_with_probability() -> None:
    goal = GoalConfig(name="retire", target=1_000.0, horizon_years=3, p_min=0.6, weight=1.0)
    parameters = GoalParameters.from_mapping(
        {
            "investor": "adjust",
            "contrib_monthly": 0.0,
            "contribution_growth": 0.0,
            "initial_wealth": 100_000.0,
        }
    )
    periods = goal.horizon_years * 12
    optimistic = RegimeCurves(
        base_mu=np.full(periods, 0.01),
        base_sigma=np.full(periods, 0.001),
        crisis_mu=np.full(periods, 0.005),
        crisis_sigma=np.full(periods, 0.001),
        crisis_probability=np.zeros(periods),
    )
    pessimistic = RegimeCurves(
        base_mu=np.full(periods, -0.01),
        base_sigma=np.full(periods, 0.001),
        crisis_mu=np.full(periods, -0.02),
        crisis_sigma=np.full(periods, 0.001),
        crisis_probability=np.ones(periods),
    )
    success = simulate_goals(
        [goal],
        draws=128,
        seed=7,
        parameters=parameters,
        assumptions=optimistic,
    )
    failure = simulate_goals(
        [goal],
        draws=128,
        seed=7,
        parameters=parameters,
        assumptions=pessimistic,
    )
    success_path = success.glidepaths[goal.name]
    failure_path = failure.glidepaths[goal.name]
    assert float(success_path["te_budget_scale"].iloc[-1]) < 1.0
    assert float(failure_path["te_budget_scale"].iloc[-1]) > 1.0


def test_goal_monte_carlo_returns_serialisable_payload() -> None:
    goals = [GoalConfig(name="goal", target=25_000.0, horizon_years=4, p_min=0.5, weight=1.0)]
    parameters = _sample_parameters()
    payload = goal_monte_carlo(parameters, goals, draws=256, seed=5)
    assert set(payload) == {
        "results",
        "glidepaths",
        "fan_charts",
        "weighted_probability",
        "seed",
        "draws",
    }
    assert isinstance(payload["results"], pd.DataFrame)
    assert payload["draws"] == 256


def test_run_goal_monte_carlo_writes_artifacts(tmp_path: Path) -> None:
    goals = load_goal_configs_from_yaml("configs/goals.yml")
    parameters = load_goal_parameters("configs/params.yml")
    summary, artifacts = run_goal_monte_carlo(
        goals,
        draws=512,
        seed=7,
        parameters=parameters,
        output_dir=tmp_path,
    )
    assert isinstance(summary, GoalSimulationSummary)
    assert summary.draws == 512
    assert artifacts.summary_csv.exists()
    assert artifacts.report_pdf.exists()
    assert artifacts.fan_chart_csv.exists()
    exported = pd.read_csv(artifacts.summary_csv)
    assert {"goal", "probability", "passes"}.issubset(exported.columns)
