from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.reporting.plots import plot_attribution, plot_fan_chart, plot_turnover_costs


def test_plot_fan_chart_creates_file(tmp_path: Path) -> None:
    index = pd.date_range("2024-01-31", periods=3, freq=pd.offsets.MonthEnd())
    data = pd.DataFrame({"path_0": [1.0, 1.02, 1.05], "path_1": [1.0, 0.99, 1.01]}, index=index)
    output = plot_fan_chart(data, path=tmp_path)
    assert output.exists()


def test_plot_attribution_requires_data(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        plot_attribution(pd.DataFrame(), path=tmp_path)

    index = pd.date_range("2024-01-31", periods=2, freq=pd.offsets.MonthEnd())
    contributions = pd.DataFrame({"Growth": [0.001, 0.002], "Value": [0.0, 0.001]}, index=index)
    output = plot_attribution(contributions, path=tmp_path, stacked=False)
    assert output.exists()


def test_plot_turnover_costs_index_alignment(tmp_path: Path) -> None:
    index = pd.date_range("2024-01-31", periods=3, freq=pd.offsets.MonthEnd())
    turnover = pd.Series([0.05, 0.04, 0.03], index=index)
    costs = pd.Series([0.0004, 0.0003, 0.0002], index=index)
    output = plot_turnover_costs(turnover, costs, path=tmp_path)
    assert output.exists()
    with pytest.raises(ValueError):
        plot_turnover_costs(turnover, costs.shift(1).dropna(), path=tmp_path)
