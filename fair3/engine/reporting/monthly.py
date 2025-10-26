from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from fair3.engine.reporting.analytics import acceptance_gates, attribution_ic
from fair3.engine.reporting.plots import (
    plot_attribution,
    plot_fan_chart,
    plot_fanchart,
    plot_turnover_costs,
)
from fair3.engine.utils.io import artifact_path, ensure_dir, safe_path_segment, write_json
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
    """Inputs required to build the monthly report.

    Attributes:
      returns: Series of portfolio returns indexed by date.
      weights: Instrument weights aligned with ``returns``.
      factor_contributions: Factor attribution series indexed by date.
      instrument_contributions: Instrument attribution series indexed by date.
      turnover: Realised turnover series.
      costs: Trading cost series.
      taxes: Tax series aligned with ``costs``.
      compliance_flags: Mapping of compliance checks to boolean flags.
      cluster_map: Optional mapping of cluster names to instrument lists.
      instrument_returns: Optional instrument return panel for attribution IC.
      factor_returns: Optional factor return panel for attribution IC.
      bootstrap_metrics: Optional bootstrap metrics DataFrame with columns
        such as ``max_drawdown`` and ``cagr``.
      thresholds: Optional acceptance gate thresholds.
    """

    returns: pd.Series
    weights: pd.DataFrame
    factor_contributions: pd.DataFrame
    instrument_contributions: pd.DataFrame
    turnover: pd.Series
    costs: pd.Series
    taxes: pd.Series
    compliance_flags: Mapping[str, bool]
    cluster_map: Mapping[str, Sequence[str]] | None = None
    instrument_returns: pd.DataFrame | None = None
    factor_returns: pd.DataFrame | None = None
    bootstrap_metrics: pd.DataFrame | None = None
    thresholds: Mapping[str, float] | None = None


@dataclass
class MonthlyReportArtifacts:
    """Artifacts produced by :func:`generate_monthly_report`.

    Attributes:
      metrics_csv: Path to the CSV containing summary metrics.
      metrics_json: Path to the JSON file with the same metrics.
      attribution_csv: CSV with factor and instrument attribution tables.
      compliance_json: JSON file encoding compliance flags.
      fan_chart: PNG chart showing the wealth fan chart.
      attribution_plot: PNG chart with factor attribution.
      turnover_plot: PNG chart with turnover and costs.
      cluster_csv: CSV with cluster-level weights.
      summary_json: JSON summary with cost and turnover totals.
      metric_fan_charts: Mapping of metric name to PNG artefact path.
      acceptance_json: JSON file with acceptance gate evaluation.
      report_pdf: PDF summarising metrics, compliance, and charts.
      attribution_ic_csv: Optional CSV with attribution and IC statistics.
    """

    metrics_csv: Path
    metrics_json: Path
    attribution_csv: Path
    compliance_json: Path
    fan_chart: Path
    attribution_plot: Path
    turnover_plot: Path
    cluster_csv: Path
    summary_json: Path
    metric_fan_charts: dict[str, Path]
    acceptance_json: Path
    report_pdf: Path
    attribution_ic_csv: Path | None = None


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


def _metric_paths(
    draw_matrix: np.ndarray,
    *,
    periods_per_year: int = 12,
    alpha: float = 0.95,
    edar_window: int = 36,
) -> dict[str, np.ndarray]:
    """Compute rolling statistics for each bootstrap path.

    Args:
      draw_matrix: Matrix of bootstrap returns shaped ``(n_periods, n_paths)``.
      periods_per_year: Number of periods per year (12 for monthly data).
      alpha: Tail probability used for CVaR and EDaR calculations.
      edar_window: Window, in periods, used when computing EDaR.

    Returns:
      Dictionary mapping metric names to arrays shaped
      ``(n_periods, n_paths)`` containing the evolution of each metric.
    """

    n_obs, n_paths = draw_matrix.shape
    counts = np.arange(1, n_obs + 1, dtype="float64").reshape(-1, 1)

    cumulative = np.cumsum(draw_matrix, axis=0)
    cumulative_sq = np.cumsum(draw_matrix**2, axis=0)
    mean = cumulative / counts
    variance = np.maximum(cumulative_sq / counts - mean**2, 0.0)
    std = np.sqrt(variance)
    sharpe = np.zeros_like(draw_matrix)
    valid = std > 0
    sharpe[valid] = mean[valid] / std[valid] * np.sqrt(periods_per_year)

    wealth = np.cumprod(1.0 + draw_matrix, axis=0)
    years = counts / float(periods_per_year)
    with np.errstate(divide="ignore", invalid="ignore"):
        cagr = np.where(years > 0, wealth ** (1.0 / years) - 1.0, 0.0)

    peaks = np.maximum.accumulate(wealth, axis=0)
    drawdowns = wealth / peaks - 1.0
    max_drawdown = np.minimum.accumulate(drawdowns, axis=0)

    cvar = np.zeros_like(draw_matrix)
    for idx in range(n_obs):
        horizon = np.sort(draw_matrix[: idx + 1, :], axis=0)
        cutoff = max(1, int(np.ceil((1 - alpha) * (idx + 1))))
        tail = horizon[:cutoff, :]
        cvar[idx, :] = tail.mean(axis=0)

    edar = np.zeros_like(draw_matrix)
    for path_idx in range(n_paths):
        series = pd.Series(draw_matrix[:, path_idx])
        for idx in range(n_obs):
            subset = series.iloc[: idx + 1]
            edar[idx, path_idx] = _edar(subset, window=edar_window, alpha=alpha)

    return {
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "cvar": cvar,
        "edar": edar,
        "cagr": cagr,
    }


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
    resampled = series.resample("ME")
    if method == "sum":
        return resampled.sum()
    if method == "product":
        return resampled.apply(lambda x: (1 + x).prod() - 1)
    raise ValueError(f"Unknown aggregation method: {method}")


def simulate_fan_chart(
    returns: pd.Series,
    *,
    seed: int,
    paths: int = 256,
    return_paths: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate bootstrap wealth paths for fan chart plotting.

    Args:
      returns: Series of returns sampled to build the wealth paths.
      seed: Deterministic seed used for the pseudo-random generator.
      paths: Number of bootstrap paths to generate.
      return_paths: When ``True`` the function also returns the sampled
        returns alongside the wealth paths.

    Returns:
      Either a DataFrame with wealth paths or a tuple ``(wealth, returns)``
      when ``return_paths`` is set.

    Raises:
      ValueError: If ``returns`` is empty.
    """

    rng = generator_from_seed(seed)
    if returns.empty:
        raise ValueError("returns cannot be empty for simulation")
    ret_values = returns.to_numpy()
    months = len(returns)
    draws = rng.choice(ret_values, size=(months, paths), replace=True)
    wealth = np.cumprod(1 + draws, axis=0)
    index = returns.index
    columns = [f"path_{i}" for i in range(paths)]
    wealth_df = pd.DataFrame(wealth, index=index, columns=columns)
    if return_paths:
        draw_df = pd.DataFrame(draws, index=index, columns=columns)
        return wealth_df, draw_df
    return wealth_df


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


def _render_metric_fan_chart(
    matrix: np.ndarray,
    dates: pd.DatetimeIndex,
    *,
    name: str,
    report_root: Path,
    ylabel: str,
) -> Path:
    """Render a metric fan chart and return the artefact path.

    Args:
      matrix: Metric values shaped ``(n_periods, n_paths)``.
      dates: Date index aligned with the first axis of ``matrix``.
      name: Base name used to build the output filename.
      report_root: Directory where artefacts will be stored.
      ylabel: Label used for the y-axis.

    Returns:
      Path pointing to the generated PNG chart.
    """

    quantiles = np.quantile(matrix, [0.05, 0.5, 0.95], axis=1)
    output = report_root / f"{name}_fan.png"
    fig, axis = plt.subplots(figsize=(8.0, 4.5), constrained_layout=True)
    plot_fanchart(
        axis,
        dates.to_pydatetime(),
        quantiles[1],
        quantiles[0],
        quantiles[2],
        title=f"{name.upper()} fan",
        ylabel=ylabel,
    )
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def _build_pdf_report(
    period_label: str,
    metrics: Mapping[str, float],
    compliance: Mapping[str, bool],
    acceptance: Mapping[str, bool | float],
    charts: Sequence[Path],
    *,
    path: Path,
) -> Path:
    """Generate a compact PDF summary combining metrics and charts.

    Args:
      period_label: Human readable period label (e.g., ``"2024-01:2024-06"``).
      metrics: Mapping of scalar metrics included in the PDF summary.
      compliance: Compliance flags reported as booleans.
      acceptance: Acceptance gate evaluation containing boolean flags.
      charts: Sequence of chart artefacts that will be embedded in the PDF.
      path: Destination path for the PDF.

    Returns:
      Path to the generated PDF artefact.
    """

    ensure_dir(path.parent)
    page_width, page_height = A4
    pdf = canvas.Canvas(str(path), pagesize=A4)
    margin_x = 40
    y = page_height - 50

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin_x, y, f"FAIR-III Monthly Report: {period_label}")
    y -= 28

    pdf.setFont("Helvetica", 10)
    for key, value in metrics.items():
        pdf.drawString(margin_x, y, f"{key}: {value:.4f}")
        y -= 14

    y -= 8
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Compliance flags")
    y -= 18
    pdf.setFont("Helvetica", 10)
    for key, value in compliance.items():
        pdf.drawString(margin_x, y, f"{key}: {'PASS' if value else 'FAIL'}")
        y -= 14

    y -= 8
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Acceptance gates")
    y -= 18
    pdf.setFont("Helvetica", 10)
    drawdown_status = "PASS" if acceptance["max_drawdown_gate"] else "FAIL"
    pdf.drawString(
        margin_x,
        y,
        f"MaxDD prob={acceptance['max_drawdown_probability']:.3f} gate={drawdown_status}",
    )
    y -= 14
    cagr_status = "PASS" if acceptance["cagr_gate"] else "FAIL"
    pdf.drawString(
        margin_x,
        y,
        f"CAGR LB={acceptance['cagr_lower_bound']:.3%} gate={cagr_status}",
    )
    y -= 20

    for chart in charts:
        image = ImageReader(str(chart))
        height = 180
        width = page_width - 2 * margin_x
        if y - height < 60:
            pdf.showPage()
            y = page_height - 60
        pdf.drawImage(
            image,
            margin_x,
            y - height,
            width=width,
            height=height,
            preserveAspectRatio=True,
        )
        y -= height + 24

    pdf.save()
    return path


def generate_monthly_report(
    inputs: MonthlyReportInputs,
    *,
    period_label: str,
    output_dir: Path | str | None = None,
    seed: int = 0,
) -> MonthlyReportArtifacts:
    """Generate the monthly performance report and return produced artefacts."""

    base_dir = ensure_dir(output_dir or artifact_path("reports", create=True))
    safe_label = safe_path_segment(period_label)
    report_root = ensure_dir(base_dir / safe_label)

    returns_monthly = _aggregate_monthly(inputs.returns, method="product")
    metrics = compute_monthly_metrics(returns_monthly)

    metrics_csv = report_root / "metrics.csv"
    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(metrics_csv, index=False)
    metrics_json = report_root / "metrics.json"
    write_json(metrics, metrics_json)

    attribution = inputs.factor_contributions.sort_index().resample("ME").sum()
    instr_attr = inputs.instrument_contributions.sort_index().resample("ME").sum()
    attribution_df = pd.concat({"factors": attribution, "instruments": instr_attr}, axis=1)
    attribution_csv = report_root / "attribution.csv"
    attribution_df.to_csv(attribution_csv)

    compliance_json = report_root / "compliance.json"
    write_json({k: bool(v) for k, v in inputs.compliance_flags.items()}, compliance_json)

    wealth_result = simulate_fan_chart(returns_monthly, seed=seed, return_paths=True)
    wealth_paths, return_paths = wealth_result
    fan_chart = plot_fan_chart(
        wealth_paths,
        title=f"Portfolio wealth fan ({period_label})",
        path=report_root,
    )

    metric_paths = _metric_paths(return_paths.to_numpy(copy=False))
    metric_labels = {
        "sharpe": "Sharpe",
        "max_drawdown": "Max drawdown",
        "cvar": "CVaR",
        "edar": "EDaR",
        "cagr": "CAGR",
    }
    metric_fans: dict[str, Path] = {}
    for key, label in metric_labels.items():
        metric_fans[key] = _render_metric_fan_chart(
            metric_paths[key],
            returns_monthly.index,
            name=key,
            report_root=report_root,
            ylabel=label,
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
        inputs.weights.sort_index().resample("ME").mean(), inputs.cluster_map
    )
    cluster_csv = report_root / "erc_clusters.csv"
    cluster_weights.to_csv(cluster_csv)

    summary = {
        "turnover_total": round(float(turnover_monthly.sum()), 4),
        "cost_total": round(float(cost_monthly.sum()), 4),
    }
    summary_json = report_root / "summary.json"
    write_json(summary, summary_json)

    thresholds = {
        "max_drawdown_threshold": -0.25,
        "cagr_target": 0.03,
    }
    if inputs.thresholds:
        thresholds.update({k: float(v) for k, v in inputs.thresholds.items()})

    acceptance_payload = {
        "max_drawdown": metric_paths["max_drawdown"][-1, :],
        "cagr": metric_paths["cagr"][-1, :],
    }
    if inputs.bootstrap_metrics is not None:
        frame = inputs.bootstrap_metrics
        if "max_drawdown" in frame.columns:
            acceptance_payload["max_drawdown"] = frame["max_drawdown"].to_numpy()
        if "cagr" in frame.columns:
            acceptance_payload["cagr"] = frame["cagr"].to_numpy()

    acceptance_summary = acceptance_gates(acceptance_payload, thresholds)
    acceptance_json = report_root / "acceptance.json"
    write_json(
        {
            "max_drawdown_probability": acceptance_summary["max_drawdown_probability"],
            "max_drawdown_gate": acceptance_summary["max_drawdown_gate"],
            "cagr_lower_bound": acceptance_summary["cagr_lower_bound"],
            "cagr_gate": acceptance_summary["cagr_gate"],
            "passes": acceptance_summary["passes"],
        },
        acceptance_json,
    )

    attribution_ic_path: Path | None = None
    if inputs.instrument_returns is not None and inputs.factor_returns is not None:
        ic_frame = attribution_ic(
            inputs.weights.sort_index(),
            inputs.instrument_returns.sort_index(),
            inputs.factor_returns.sort_index(),
        )
        attribution_ic_path = report_root / "attribution_ic.csv"
        ic_frame.to_csv(attribution_ic_path)

    charts_for_pdf = [fan_chart]
    charts_for_pdf.extend(metric_fans.values())
    charts_for_pdf.extend([attribution_plot, turnover_plot])
    report_pdf = _build_pdf_report(
        period_label,
        metrics,
        {k: bool(v) for k, v in inputs.compliance_flags.items()},
        acceptance_summary,
        charts_for_pdf,
        path=report_root / "monthly_report.pdf",
    )

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
        metric_fan_charts=metric_fans,
        acceptance_json=acceptance_json,
        report_pdf=report_pdf,
        attribution_ic_csv=attribution_ic_path,
    )
