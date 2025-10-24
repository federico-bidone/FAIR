from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fair3.engine.utils.io import artifact_path, ensure_dir

__all__ = [
    "plot_fan_chart",
    "plot_attribution",
    "plot_turnover_costs",
]

# Ensure headless environments default to Agg
matplotlib.use("Agg", force=True)


def _resolve_path(path: Path | str | None, filename: str) -> Path:
    if path is None:
        return artifact_path("reports", filename)
    path_obj = Path(path)
    if path_obj.is_dir():
        ensure_dir(path_obj)
        return path_obj / filename
    ensure_dir(path_obj.parent)
    return path_obj


def plot_fan_chart(
    wealth_paths: pd.DataFrame,
    percentiles: Sequence[float] = (0.1, 0.5, 0.9),
    *,
    path: Path | str | None = None,
    title: str | None = None,
) -> Path:
    """Plot a fan chart of cumulative wealth percentiles.

    Parameters
    ----------
    wealth_paths:
        DataFrame indexed by date with scenario wealth paths in columns.
    percentiles:
        Percentiles expressed as decimals (0–1) to plot. Must include a
        central tendency (e.g., 0.5) for the median line.
    path:
        Optional custom output path. When a directory is provided the file
        `fan_chart.png` will be written inside it.
    title:
        Optional title for the figure.
    """

    if wealth_paths.empty:
        raise ValueError("wealth_paths must contain at least one scenario")
    pct = sorted(percentiles)
    if not pct:
        raise ValueError("percentiles must be a non-empty sequence")

    output = _resolve_path(path, "fan_chart.png")

    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    quantiles = wealth_paths.quantile(pct, axis=1).T
    lower = quantiles.iloc[:, 0]
    median = quantiles.iloc[:, len(pct) // 2]
    upper = quantiles.iloc[:, -1]

    ax.fill_between(quantiles.index, lower, upper, color="#88c0d0", alpha=0.4, label="fan band")
    ax.plot(quantiles.index, median, color="#2e3440", linewidth=2.0, label="median")
    ax.set_ylabel("Wealth (base=1.0)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False)
    if title:
        ax.set_title(title)
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
    """Plot factor or instrument attribution over time."""

    if contributions.empty:
        raise ValueError("contributions must contain data")

    output = _resolve_path(path, "attribution.png")
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    if stacked:
        bottom = np.zeros(len(contributions))
        for col in contributions.columns:
            values = contributions[col].to_numpy()
            ax.bar(contributions.index, values, bottom=bottom, label=col)
            bottom = bottom + values
    else:
        for col in contributions.columns:
            ax.plot(contributions.index, contributions[col], label=col)
    ax.set_ylabel("Contribution")
    ax.set_xlabel("Date")
    ax.legend(frameon=False, ncol=2)
    if title:
        ax.set_title(title)
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
    """Plot realised turnover and cost series."""

    if len(turnover) != len(costs):
        raise ValueError("turnover and costs must have the same length")
    if not turnover.index.equals(costs.index):
        raise ValueError("turnover and costs must share the same index")

    output = _resolve_path(path, "turnover_costs.png")
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    label_map = labels or {"turnover": "Turnover", "costs": "Trading costs"}
    ax.bar(
        turnover.index,
        turnover.values,
        color="#5e81ac",
        alpha=0.7,
        label=label_map.get("turnover", "Turnover"),
    )
    ax.plot(
        costs.index,
        costs.values,
        color="#bf616a",
        linewidth=2.0,
        marker="o",
        label=label_map.get("costs", "Costs"),
    )
    ax.set_ylabel("Value")
    ax.set_xlabel("Date")
    ax.legend(frameon=False)
    if title:
        ax.set_title(title)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output
