# Reporting Module

The reporting package aggregates outputs produced by the portfolio engine. In
addition to the audit helpers introduced earlier, it now exposes a monthly
report builder with deterministic plotting utilities to satisfy FAIR-III’s
retail disclosure requirements.

## Public API

### `fair3.engine.reporting.audit`
- `ensure_audit_dir(audit_dir=None)`
- `copy_seed_snapshot(seed_path="audit/seeds.yml", audit_dir=None, timestamp=None)`
- `snapshot_configs(config_paths, audit_dir=None, timestamp=None)`
- `record_checksums(targets, audit_dir=None, timestamp=None)`
- `append_change_log(message, audit_dir=None, timestamp=None)`
- `run_audit_snapshot(seed_path=..., config_paths=(), checksums=None, note=None, audit_dir=None, timestamp=None)`

### `fair3.engine.reporting.monthly`
- `MonthlyReportInputs`
- `MonthlyReportArtifacts`
- `compute_monthly_metrics(returns)`
- `generate_monthly_report(inputs, period_label, output_dir=None, seed=0)`
- `simulate_fan_chart(returns, seed, paths=256, return_paths=False)`
- `acceptance_gates(metrics, thresholds, alpha_drawdown=None, alpha_cagr=None)`
- `attribution_ic(weights, returns, factors, window=12)`

### `fair3.engine.reporting.plots`
- `plot_fan_chart(wealth_paths, percentiles=(0.05,0.5,0.95), path=None)`
- `plot_fanchart(axis, dates, median, lower, upper, title=None, ylabel=None)`
- `plot_attribution(contributions, path=None, stacked=True)`
- `plot_turnover_costs(turnover, costs, path=None)`

## CLI / Pipeline Usage

Within the `fair3 report --period YYYY-MM:YYYY-MM --monthly` command the CLI
loads PIT artefacts, assembles the `MonthlyReportInputs` structure, and emits
CSV/JSON summaries, PNG plots, acceptance-gate diagnostics, and a PDF snapshot
inside `artifacts/reports/<period>/`. The helper accepts a custom `output_dir`
to facilitate regression tests and notebooks.

```python
from fair3.engine.reporting import MonthlyReportInputs, generate_monthly_report

artifacts = generate_monthly_report(
    MonthlyReportInputs(
        returns=returns_series,
        weights=weights_df,
        factor_contributions=factor_attr,
        instrument_contributions=instrument_attr,
        turnover=turnover_series,
        costs=cost_series,
        taxes=tax_series,
        compliance_flags={"ucits": True, "no_trade": True},
        instrument_returns=instrument_returns,
        factor_returns=factor_returns,
        bootstrap_metrics=bootstrap_metrics,
        thresholds={"max_drawdown_threshold": -0.25, "cagr_target": 0.03},
    ),
    period_label="2025-01:2025-06",
    seed=42,
)
print("Metrics saved to", artifacts.metrics_csv)
print("Acceptance gates", artifacts.acceptance_json)
print("Monthly PDF", artifacts.report_pdf)
```

## Common Errors & Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| Missing PNG outputs | Matplotlib backend not set in headless CI | The module forces `Agg`, ensure dependency installed |
| Empty aggregation frames | Upstream ETL did not populate PIT artefacts | Verify ETL step and date filters before running reports |
| Non-monotonic dates | Upstream merges produced unsorted indices | Call `.sort_index()` prior to feeding the report inputs |

## Trace Hooks

Audit helpers and the monthly generator respond to the global `--trace` flag by
reusing the logger configured via `fair3.engine.logging.setup_logger`. Include
artefact paths in trace logs for quick diagnosis.
