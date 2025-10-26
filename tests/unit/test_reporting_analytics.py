from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from fair3.engine.reporting import acceptance_gates, attribution_ic
from fair3.engine.reporting.plots import plot_fanchart


def test_acceptance_gates_pass_fail() -> None:
    metrics = {
        "max_drawdown": np.array([-0.21, -0.22, -0.19, -0.23, -0.20]),
        "cagr": np.array([0.06, 0.05, 0.055, 0.052, 0.051]),
    }
    thresholds = {"max_drawdown_threshold": -0.25, "cagr_target": 0.04}
    summary = acceptance_gates(metrics, thresholds)
    assert summary["max_drawdown_gate"]
    assert summary["cagr_gate"]
    assert summary["passes"]


def test_acceptance_gates_missing_keys() -> None:
    metrics = {"max_drawdown": np.array([-0.2, -0.21])}
    thresholds = {"cagr_target": 0.03}
    with pytest.raises(KeyError):
        acceptance_gates(metrics, thresholds)


def test_attribution_ic_shapes() -> None:
    index = pd.date_range("2024-01-31", periods=4, freq=pd.offsets.MonthEnd())
    weights = pd.DataFrame(
        [[0.6, 0.4], [0.55, 0.45], [0.5, 0.5], [0.52, 0.48]],
        index=index,
        columns=["EQT", "BND"],
    )
    returns = pd.DataFrame(
        [[0.01, 0.002], [0.008, 0.003], [0.009, 0.0025], [0.007, 0.0028]],
        index=index,
        columns=["EQT", "BND"],
    )
    factors = pd.DataFrame(
        [[0.005, 0.004], [0.004, 0.003], [0.006, 0.002], [0.005, 0.0025]],
        index=index,
        columns=["Growth", "Value"],
    )
    frame = attribution_ic(weights, returns, factors, window=2)
    assert ("instrument_contribution", "EQT") in frame.columns
    assert ("factor_contribution", "Growth") in frame.columns
    assert ("information_coefficient", "Value") in frame.columns
    assert frame.shape[0] == len(index)


def test_plot_fanchart_length_mismatch() -> None:
    fig, axis = plt.subplots()
    with pytest.raises(ValueError):
        plot_fanchart(axis, [1, 2], [0.0], [0.0, 0.0], [0.1, 0.2])
    plt.close(fig)
