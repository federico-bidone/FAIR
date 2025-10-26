from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fair3.engine.reporting import (
    MonthlyReportInputs,
    compute_monthly_metrics,
    generate_monthly_report,
    simulate_fan_chart,
)


def _sample_inputs() -> MonthlyReportInputs:
    index = pd.date_range("2024-01-31", periods=6, freq=pd.offsets.MonthEnd())
    returns = pd.Series([0.01, -0.005, 0.007, 0.012, -0.004, 0.009], index=index)
    weights = pd.DataFrame(
        [
            [0.4, 0.3, 0.2, 0.1],
            [0.35, 0.33, 0.2, 0.12],
            [0.32, 0.35, 0.2, 0.13],
            [0.3, 0.36, 0.22, 0.12],
            [0.31, 0.34, 0.23, 0.12],
            [0.33, 0.33, 0.22, 0.12],
        ],
        index=index,
        columns=["EQT", "BND", "ALT", "CASH"],
    )
    factor_attr = pd.DataFrame(
        {
            "Growth": [0.002, 0.0015, 0.001, 0.0022, 0.0011, 0.0018],
            "Value": [0.001, 0.0008, 0.0012, 0.0009, 0.001, 0.0007],
        },
        index=index,
    )
    instr_attr = pd.DataFrame(
        {
            "EQT": [0.003, 0.0025, 0.002, 0.003, 0.0022, 0.0027],
            "BND": [0.001, 0.0009, 0.0011, 0.0008, 0.001, 0.0009],
            "ALT": [0.0005, 0.0006, 0.0004, 0.0005, 0.0006, 0.0005],
            "CASH": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        },
        index=index,
    )
    instrument_returns = pd.DataFrame(
        {
            "EQT": [0.01, -0.004, 0.007, 0.012, -0.003, 0.009],
            "BND": [0.002, 0.0015, 0.0021, 0.0019, 0.0022, 0.002],
            "ALT": [0.001, 0.0012, 0.0008, 0.0011, 0.0013, 0.001],
            "CASH": [0.0002, 0.0002, 0.0002, 0.0002, 0.0002, 0.0002],
        },
        index=index,
    )
    factor_returns = pd.DataFrame(
        {
            "Growth": [0.008, -0.003, 0.006, 0.009, -0.002, 0.007],
            "Value": [0.004, 0.003, 0.0042, 0.0035, 0.0041, 0.0036],
        },
        index=index,
    )
    bootstrap_metrics = pd.DataFrame(
        {
            "max_drawdown": [-0.2, -0.22, -0.18, -0.21, -0.19],
            "cagr": [0.045, 0.047, 0.05, 0.044, 0.049],
        }
    )
    thresholds = {
        "max_drawdown_threshold": -0.25,
        "cagr_target": 0.03,
        "max_drawdown_exceedance": 0.05,
        "cagr_alpha": 0.05,
    }
    turnover = pd.Series([0.05, 0.03, 0.04, 0.02, 0.01, 0.03], index=index)
    costs = pd.Series([0.0003, 0.0002, 0.00025, 0.0002, 0.00015, 0.0002], index=index)
    taxes = pd.Series([0.0001, 0.00008, 0.0001, 0.00009, 0.00007, 0.00008], index=index)
    flags = {"ucits_only": True, "no_trade_band_respected": True, "audit_complete": True}
    cluster_map = {"Equity": ["EQT"], "Rates": ["BND"], "Alts": ["ALT"], "Liquidity": ["CASH"]}
    return MonthlyReportInputs(
        returns=returns,
        weights=weights,
        factor_contributions=factor_attr,
        instrument_contributions=instr_attr,
        turnover=turnover,
        costs=costs,
        taxes=taxes,
        compliance_flags=flags,
        cluster_map=cluster_map,
        instrument_returns=instrument_returns,
        factor_returns=factor_returns,
        bootstrap_metrics=bootstrap_metrics,
        thresholds=thresholds,
    )


def test_compute_monthly_metrics_structure() -> None:
    inputs = _sample_inputs()
    metrics = compute_monthly_metrics(inputs.returns)
    assert set(metrics) == {"cagr", "sharpe", "max_drawdown", "cvar_95", "edar_3y"}
    assert metrics["max_drawdown"] <= 0.0


def test_simulate_fan_chart_deterministic() -> None:
    inputs = _sample_inputs()
    wealth_a, draws_a = simulate_fan_chart(inputs.returns, seed=42, paths=16, return_paths=True)
    wealth_b, draws_b = simulate_fan_chart(inputs.returns, seed=42, paths=16, return_paths=True)
    assert wealth_a.equals(wealth_b)
    assert draws_a.equals(draws_b)
    assert wealth_a.shape == (len(inputs.returns), 16)
    assert draws_a.shape == (len(inputs.returns), 16)


def test_generate_monthly_report_outputs(tmp_path: Path) -> None:
    inputs = _sample_inputs()
    artifacts = generate_monthly_report(
        inputs,
        period_label="2024-01:2024-06",
        output_dir=tmp_path,
        seed=7,
    )
    for path in (
        artifacts.metrics_csv,
        artifacts.metrics_json,
        artifacts.attribution_csv,
        artifacts.compliance_json,
        artifacts.fan_chart,
        artifacts.attribution_plot,
        artifacts.turnover_plot,
        artifacts.cluster_csv,
        artifacts.summary_json,
        artifacts.acceptance_json,
        artifacts.report_pdf,
    ):
        assert path.exists(), f"Missing artefact {path}"
    metrics_df = pd.read_csv(artifacts.metrics_csv)
    assert metrics_df.shape == (1, 5)
    assert set(artifacts.metric_fan_charts) == {"sharpe", "max_drawdown", "cvar", "edar", "cagr"}
    for chart in artifacts.metric_fan_charts.values():
        assert chart.exists()
    payload = json.loads(artifacts.acceptance_json.read_text(encoding="utf-8"))
    assert set(payload) == {
        "max_drawdown_probability",
        "max_drawdown_gate",
        "cagr_lower_bound",
        "cagr_gate",
        "passes",
    }
    assert artifacts.report_pdf.stat().st_size > 0
