# Engine modules

> Strumento informativo/educational; non costituisce consulenza finanziaria o raccomandazione.

`fair3.engine` houses the domain logic for ingest, transformation, factor
construction, estimation, allocation, mapping, regime detection, execution,
reporting, QA, robustness, and shared utilities.  Every submodule exposes typed
functions designed for both CLI orchestration and notebook experimentation while
maintaining point-in-time discipline and deterministic seeding.

## Submodule map
- `ingest/`: source-specific fetchers derived from `BaseCSVFetcher`, SQLite/Parquet
  persistence helpers, and registry wiring.
- `etl/`: PIT cleaning, Parquet schema enforcement, and SQLite upserts.
- `factors/`: factor builders, validation harnesses, and metadata governance.
- `estimates/`: mean/variance engines, PSD/SPD projections, and blend logs.
- `allocators/`: portfolio generators (Max-Sharpe, HRP, DRO, CVaR-ERC) with
  meta-mix orchestration.
- `mapping/`: rolling beta estimation, liquidity caps, and tracking-error guards.
- `regime/`: committee-based crisis probability estimation with hysteresis.
- `execution/`: lot sizing, Almgren–Chriss costs, and Italian tax heuristics.
- `reporting/`: monthly dashboards, fan charts, acceptance gates, and PDF output.
- `goals/`: regime-aware Monte Carlo goal engine with glidepath logic.
- `qa/`: deterministic QA dataset synthesis and acceptance diagnostics.
- `robustness/`: bootstrap/replay lab and ablation drivers.
- `utils/`: shared helpers (logging, seeds, IO, timezone management).

## Contribution guidelines
- Add docstrings to modules, classes, and functions with explicit `Args`,
  `Returns`, and `Raises` sections even when default behaviour is simple.
- Avoid hidden state; pass explicit paths, configs, and seeds into helpers so
  CLI commands remain idempotent.
- Capture licence metadata, checksums, and timezone/currency context in all
  ingest and ETL outputs.
