"""Reporting utilities for FAIR-III."""

from . import audit
from .analytics import acceptance_gates, attribution_ic
from .monthly import (
    MonthlyReportArtifacts,
    MonthlyReportInputs,
    compute_monthly_metrics,
    generate_monthly_report,
    simulate_fan_chart,
)
from .plots import plot_attribution, plot_fan_chart, plot_fanchart, plot_turnover_costs

__all__ = [
    "audit",
    "MonthlyReportArtifacts",
    "MonthlyReportInputs",
    "compute_monthly_metrics",
    "generate_monthly_report",
    "simulate_fan_chart",
    "acceptance_gates",
    "attribution_ic",
    "plot_attribution",
    "plot_fan_chart",
    "plot_fanchart",
    "plot_turnover_costs",
]
