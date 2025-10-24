from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from hypothesis import given
from hypothesis import strategies as st

from fair3.engine.reporting import (
    MonthlyReportInputs,
    compute_monthly_metrics,
    generate_monthly_report,
)

RETURNS_STRATEGY = st.lists(
    st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
    min_size=3,
    max_size=24,
)


@given(returns=RETURNS_STRATEGY)
def test_max_drawdown_is_non_positive(returns: list[float]) -> None:
    index = pd.date_range("2020-01-31", periods=len(returns), freq="M")
    series = pd.Series(returns, index=index)
    metrics = compute_monthly_metrics(series)
    assert metrics["max_drawdown"] <= 1e-9


def test_zero_turnover_zero_costs(tmp_path: Path) -> None:
    index = pd.date_range("2024-01-31", periods=3, freq="M")
    zeros = pd.Series(0.0, index=index)
    inputs = MonthlyReportInputs(
        returns=zeros,
        weights=pd.DataFrame(0.25, index=index, columns=["A", "B", "C", "D"]),
        factor_contributions=pd.DataFrame(0.0, index=index, columns=["f1", "f2"]),
        instrument_contributions=pd.DataFrame(0.0, index=index, columns=["A", "B", "C", "D"]),
        turnover=zeros,
        costs=zeros,
        taxes=zeros,
        compliance_flags={"ucits_only": True},
        cluster_map={"All": ["A", "B", "C", "D"]},
    )
    artifacts = generate_monthly_report(
        inputs,
        period_label="2024-01:2024-03",
        output_dir=tmp_path,
        seed=0,
    )
    summary = json.loads(artifacts.summary_json.read_text())
    assert summary["turnover_total"] == 0.0
    assert summary["cost_total"] == 0.0
