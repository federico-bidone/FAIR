"""Reporting utilities for FAIR-III."""

from . import audit
from .monthly import (
    MonthlyReportArtifacts,
    MonthlyReportInputs,
    compute_monthly_metrics,
    generate_monthly_report,
    simulate_fan_chart,
)
from .plots import plot_attribution, plot_fan_chart, plot_turnover_costs

__all__ = [
    "audit",
    "MonthlyReportArtifacts",
    "MonthlyReportInputs",
    "compute_monthly_metrics",
    "generate_monthly_report",
    "simulate_fan_chart",
    "plot_attribution",
    "plot_fan_chart",
    "plot_turnover_costs",
]
