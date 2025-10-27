from __future__ import annotations

# ruff: noqa: E402
"""Plotting helpers for FAIR-III reporting artefacts."""

from collections.abc import Mapping, Sequence
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.axes import Axes

from fair3.engine.utils.io import artifact_path, ensure_dir

__all__ = [
    "plot_fan_chart",
    "plot_fanchart",
    "plot_attribution",
    "plot_turnover_costs",
]

matplotlib.use("Agg", force=True)


def _resolve_path(path: Path | str | None, filename: str) -> Path:
    """Resolve an output path ensuring the parent directory exists."""

    if path is None:
        return artifact_path("reports", filename)
    path_obj = Path(path)
    if path_obj.is_dir():
        ensure_dir(path_obj)
        return path_obj / filename
    ensure_dir(path_obj.parent)
    return path_obj


def plot_fanchart(
    axis: Axes,
    dates: Sequence[pd.Timestamp] | np.ndarray,
    median: Sequence[float] | np.ndarray,
    lower: Sequence[float] | np.ndarray,
    upper: Sequence[float] | np.ndarray,
    *,
    title: str | None = None,
    ylabel: str | None = None,
) -> None:
    """Render a fan chart on an existing Matplotlib axis.

    Args:
      axis: Axis that will receive the fan chart.
      dates: Sequence of datetime-like objects shared across the series.
      median: Median (central tendency) values for each date.
      lower: Lower bound of the interval (e.g., 5th percentile).
      upper: Upper bound of the interval (e.g., 95th percentile).
      title: Optional plot title.
      ylabel: Optional label for the y-axis.

    Raises:
      ValueError: If the input sequences do not share the same length.
    """

    x = np.asarray(dates)
    m = np.asarray(median, dtype="float64")
    lo = np.asarray(lower, dtype="float64")
    hi = np.asarray(upper, dtype="float64")
    if not (len(x) == len(m) == len(lo) == len(hi)):
        raise ValueError("dates, median, lower and upper must share the same length")

    axis.fill_between(x, lo, hi, color="#88c0d0", alpha=0.35, label="interval")
    axis.plot(x, m, color="#2e3440", linewidth=2.0, label="median")
    axis.set_xlabel("Date")
    if ylabel:
        axis.set_ylabel(ylabel)
    if title:
        axis.set_title(title)
    axis.legend(frameon=False)


def plot_fan_chart(
    wealth_paths: pd.DataFrame,
    percentiles: Sequence[float] = (0.05, 0.5, 0.95),
    *,
    path: Path | str | None = None,
    title: str | None = None,
    ylabel: str = "Wealth (base=1.0)",
) -> Path:
    """Save a fan chart from wealth scenarios to disk.

    Args:
      wealth_paths: DataFrame indexed by date with scenario wealth paths in columns.
      percentiles: Percentile levels expressed as decimals in ascending order.
      path: Optional path (file or directory) for the artefact.
      title: Optional chart title.
      ylabel: Label shown on the y-axis.

    Returns:
      Path to the generated PNG artefact.

    Raises:
      ValueError: If ``wealth_paths`` is empty or percentiles are not provided.
    """

    if wealth_paths.empty:
        raise ValueError("wealth_paths must contain at least one scenario")
    pct = tuple(sorted(percentiles))
    if not pct:
        raise ValueError("percentiles must be a non-empty sequence")

    quantiles = wealth_paths.quantile(pct, axis=1).T
    centre = quantiles.iloc[:, len(pct) // 2]
    lower = quantiles.iloc[:, 0]
    upper = quantiles.iloc[:, -1]

    output = _resolve_path(path, "fan_chart.png")
    fig, axis = plt.subplots(figsize=(8.0, 4.5), constrained_layout=True)
    plot_fanchart(
        axis,
        quantiles.index.to_pydatetime(),
        centre.to_numpy(),
        lower.to_numpy(),
        upper.to_numpy(),
        title=title,
        ylabel=ylabel,
    )
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_attribution(
    contributions: pd.DataFrame,
    *,
    path: Path | str | None = None,
    title: str | None = None,
    stacked: bool = True,
) -> Path:
    """Save a bar or line plot describing attribution contributions.

    Args:
      contributions: DataFrame indexed by date with one column per component.
      path: Optional path (file or directory) for the artefact.
      title: Optional chart title.
      stacked: When ``True`` renders a stacked bar chart, otherwise a line chart.

    Returns:
      Path to the generated PNG artefact.

    Raises:
      ValueError: If ``contributions`` is empty.
    """

    if contributions.empty:
        raise ValueError("contributions must contain data")

    output = _resolve_path(path, "attribution.png")
    fig, axis = plt.subplots(figsize=(8.0, 4.5), constrained_layout=True)
    if stacked:
        bottom = np.zeros(len(contributions))
        for column in contributions.columns:
            values = contributions[column].to_numpy()
            axis.bar(contributions.index, values, bottom=bottom, label=column)
            bottom = bottom + values
    else:
        for column in contributions.columns:
            axis.plot(contributions.index, contributions[column], label=column)
    axis.set_ylabel("Contribution")
    axis.set_xlabel("Date")
    axis.legend(frameon=False, ncol=2)
    if title:
        axis.set_title(title)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def plot_turnover_costs(
    turnover: pd.Series,
    costs: pd.Series,
    *,
    path: Path | str | None = None,
    labels: Mapping[str, str] | None = None,
    title: str | None = None,
) -> Path:
    """Save a plot combining turnover columns with realised costs.

    Args:
      turnover: Series of realised turnover values.
      costs: Series of total costs aligned with ``turnover``.
      path: Optional path (file or directory) for the artefact.
      labels: Optional label overrides for the legend.
      title: Optional chart title.

    Returns:
      Path to the generated PNG artefact.

    Raises:
      ValueError: If the inputs are not aligned.
    """

    if len(turnover) != len(costs):
        raise ValueError("turnover and costs must have the same length")
    if not turnover.index.equals(costs.index):
        raise ValueError("turnover and costs must share the same index")

    output = _resolve_path(path, "turnover_costs.png")
    fig, axis = plt.subplots(figsize=(8.0, 4.5), constrained_layout=True)
    label_map = labels or {"turnover": "Turnover", "costs": "Trading costs"}
    axis.bar(
        turnover.index,
        turnover.values,
        color="#5e81ac",
        alpha=0.7,
        label=label_map.get("turnover", "Turnover"),
    )
    axis.plot(
        costs.index,
        costs.values,
        color="#bf616a",
        linewidth=2.0,
        marker="o",
        label=label_map.get("costs", "Costs"),
    )
    axis.set_ylabel("Value")
    axis.set_xlabel("Date")
    axis.legend(frameon=False)
    if title:
        axis.set_title(title)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output
