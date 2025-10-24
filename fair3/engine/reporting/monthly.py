from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.reporting.plots import (
    plot_attribution,
    plot_fan_chart,
    plot_turnover_costs,
)
from fair3.engine.utils.io import artifact_path, ensure_dir, write_json
from fair3.engine.utils.rand import generator_from_seed

__all__ = [
    "MonthlyReportInputs",
    "MonthlyReportArtifacts",
    "compute_monthly_metrics",
    "generate_monthly_report",
    "simulate_fan_chart",
]


@dataclass
class MonthlyReportInputs:
    """Inputs required to build the monthly report."""

    returns: pd.Series
    weights: pd.DataFrame
    factor_contributions: pd.DataFrame
    instrument_contributions: pd.DataFrame
    turnover: pd.Series
    costs: pd.Series
    taxes: pd.Series
    compliance_flags: Mapping[str, bool]
    cluster_map: Mapping[str, Sequence[str]] | None = None


@dataclass
class MonthlyReportArtifacts:
    """Artifacts produced by :func:`generate_monthly_report`."""

    metrics_csv: Path
    metrics_json: Path
    attribution_csv: Path
    compliance_json: Path
    fan_chart: Path
    attribution_plot: Path
    turnover_plot: Path
    cluster_csv: Path
    summary_json: Path


def _annualisation_factor(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 12.0
    diffs = np.diff(index.values.astype("datetime64[M]").astype(int))
    freq = np.median(diffs) if len(diffs) else 1
    return float(12 / max(freq, 1))


def _max_drawdown(returns: pd.Series) -> float:
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax()
    drawdown = wealth / peak - 1
    return float(drawdown.min())


def _cvar(returns: pd.Series, alpha: float = 0.95) -> float:
    if returns.empty:
        return 0.0
    cutoff = int(np.ceil((1 - alpha) * len(returns)))
    if cutoff <= 0:
        return float(returns.min())
    tail = np.sort(returns.values)[:cutoff]
    return float(np.mean(tail))


def _edar(returns: pd.Series, window: int = 36, alpha: float = 0.95) -> float:
    if returns.empty:
        return 0.0
    window = min(window, len(returns))
    if window == 0:
        return 0.0
    rolling = (1 + returns).rolling(window=window).apply(np.prod, raw=True) - 1
    horizon = rolling.dropna()
    if horizon.empty:
        horizon = pd.Series([(1 + returns).prod() - 1])
    sorted_vals = np.sort(horizon.values)
    cutoff = int(np.ceil((1 - alpha) * len(sorted_vals)))
    if cutoff <= 0:
        return float(sorted_vals.min())
    tail = sorted_vals[:cutoff]
    tail = np.minimum(tail, 0.0)
    return float(np.mean(tail))


def compute_monthly_metrics(returns: pd.Series) -> dict[str, float]:
    """Compute performance statistics from monthly returns."""

    if not isinstance(returns.index, pd.DatetimeIndex):
        raise TypeError("returns must be indexed by dates")
    if not returns.index.is_monotonic_increasing:
        returns = returns.sort_index()
    ann_factor = _annualisation_factor(returns.index)
    mean = returns.mean()
    std = returns.std(ddof=1) if len(returns) > 1 else 0.0
    sharpe = float(mean / std * np.sqrt(ann_factor)) if std > 0 else 0.0
    cagr = float((1 + returns).prod() ** (ann_factor / len(returns)) - 1) if len(returns) else 0.0
    max_dd = _max_drawdown(returns)
    cvar = _cvar(returns)
    edar = _edar(returns, window=36)
    return {
        "cagr": round(cagr, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown": round(max_dd, 4),
        "cvar_95": round(cvar, 4),
        "edar_3y": round(edar, 4),
    }


def _aggregate_monthly(series: pd.Series, method: str) -> pd.Series:
    if series.empty:
        return series
    series = series.sort_index()
    resampled = series.resample("M")
    if method == "sum":
        return resampled.sum()
    if method == "product":
        return resampled.apply(lambda x: (1 + x).prod() - 1)
    raise ValueError(f"Unknown aggregation method: {method}")


def simulate_fan_chart(returns: pd.Series, *, seed: int, paths: int = 256) -> pd.DataFrame:
    """Simulate bootstrap wealth paths for fan chart plotting."""

    rng = generator_from_seed(seed)
    if returns.empty:
        raise ValueError("returns cannot be empty for simulation")
    ret_values = returns.to_numpy()
    months = len(returns)
    draws = rng.choice(ret_values, size=(months, paths), replace=True)
    wealth = np.cumprod(1 + draws, axis=0)
    index = returns.index
    columns = [f"path_{i}" for i in range(paths)]
    return pd.DataFrame(wealth, index=index, columns=columns)


def _cluster_weights(
    weights: pd.DataFrame, cluster_map: Mapping[str, Sequence[str]] | None
) -> pd.DataFrame:
    if weights.empty:
        return weights
    if not cluster_map:
        return pd.DataFrame({"total": weights.sum(axis=1)}, index=weights.index)
    result: dict[str, pd.Series] = {}
    for name, members in cluster_map.items():
        cols = [col for col in members if col in weights.columns]
        if not cols:
            continue
        result[name] = weights[cols].sum(axis=1)
    if not result:
        result["total"] = weights.sum(axis=1)
    return pd.DataFrame(result, index=weights.index)


def generate_monthly_report(
    inputs: MonthlyReportInputs,
    *,
    period_label: str,
    output_dir: Path | str | None = None,
    seed: int = 0,
) -> MonthlyReportArtifacts:
    """Generate the monthly performance report and return produced artefacts."""

    base_dir = ensure_dir(output_dir or artifact_path("reports", create=True))
    report_root = ensure_dir(base_dir / period_label)

    returns_monthly = _aggregate_monthly(inputs.returns, method="product")
    metrics = compute_monthly_metrics(returns_monthly)

    metrics_csv = report_root / "metrics.csv"
    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(metrics_csv, index=False)
    metrics_json = report_root / "metrics.json"
    write_json(metrics, metrics_json)

    attribution = inputs.factor_contributions.sort_index().resample("M").sum()
    instr_attr = inputs.instrument_contributions.sort_index().resample("M").sum()
    attribution_df = pd.concat({"factors": attribution, "instruments": instr_attr}, axis=1)
    attribution_csv = report_root / "attribution.csv"
    attribution_df.to_csv(attribution_csv)

    compliance_json = report_root / "compliance.json"
    write_json({k: bool(v) for k, v in inputs.compliance_flags.items()}, compliance_json)

    wealth_paths = simulate_fan_chart(returns_monthly, seed=seed)
    fan_chart = plot_fan_chart(
        wealth_paths,
        title=f"Portfolio wealth fan ({period_label})",
        path=report_root,
    )

    attribution_plot = plot_attribution(
        attribution,
        title="Factor attribution",
        path=report_root,
        stacked=True,
    )

    turnover_monthly = _aggregate_monthly(inputs.turnover, method="sum")
    cost_monthly = _aggregate_monthly(inputs.costs, method="sum") + _aggregate_monthly(
        inputs.taxes, method="sum"
    )
    turnover_plot = plot_turnover_costs(
        turnover_monthly,
        cost_monthly,
        title="Turnover & costs",
        path=report_root,
    )

    cluster_weights = _cluster_weights(
        inputs.weights.sort_index().resample("M").mean(), inputs.cluster_map
    )
    cluster_csv = report_root / "erc_clusters.csv"
    cluster_weights.to_csv(cluster_csv)

    summary = {
        "turnover_total": round(float(turnover_monthly.sum()), 4),
        "cost_total": round(float(cost_monthly.sum()), 4),
    }
    summary_json = report_root / "summary.json"
    write_json(summary, summary_json)

    return MonthlyReportArtifacts(
        metrics_csv=metrics_csv,
        metrics_json=metrics_json,
        attribution_csv=attribution_csv,
        compliance_json=compliance_json,
        fan_chart=fan_chart,
        attribution_plot=attribution_plot,
        turnover_plot=turnover_plot,
        cluster_csv=cluster_csv,
        summary_json=summary_json,
    )
