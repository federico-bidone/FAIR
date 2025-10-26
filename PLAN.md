# PR-15 Plan

## Scope
- Bump the FAIR-III package to **v0.2.0** and expose the version in `fair3.__init__`.
- Lay down repository scaffolding for the v0.2 roadmap: tracked `data/raw/` and `data/clean/` folders, audit placeholders,
  README/CHANGELOG updates, and roadmap alignment.
- Align tooling with the Google Python Style Guide: configure `black` and `ruff` (docstring checks), streamline pre-commit hooks,
  and ensure pytest runs automatically.

## Design Notes
- Centralise lint/format configuration inside `pyproject.toml` to avoid drift and enforce consistent rules (100-column limit,
  Google docstring convention, Python 3.11 target).
- Preserve deterministic seeds via `audit/seeds.yml` and introduce `audit/checksums.json` as the single source of truth for data
  artefact hashes (initially empty, to be filled in later PRs).
- Document the v0.2 command surface and compliance guardrails directly in the README so future contributors inherit the UCITS/EU/IT
  framing before touching code.

## Testing & Tooling
- Pre-commit should execute `ruff`, `black`, and `pytest` to catch linting/style/test regressions locally on every commit.
- CI and developers run: `ruff check .`, `black --check .`, `pytest -q`.
- No behavioural code changes are introduced in this scaffolding PR, but smoke commands (`fair3 --help`) should remain unaffected.


# PR-18 Plan (Regime Engine v2)

## Scope
- Replace the legacy committee with a deterministic HMM/HSMM implementation powered by `hmmlearn`.
- Extend hysteresis to support activation/deactivation streaks and expose new knobs in `configs/thresholds.yml`.
- Provide a full CLI command (`fair3 regime`) that loads the clean panel, persists artefacts under `artifacts/regime/` and emits structured metrics.

## Design Notes
- Introduce `regime_probability(panel, cfg, seed)` returning component diagnostics plus the combined crisis probability; keep `crisis_probability` as a compatibility wrapper.
- Build a regime pipeline orchestrator (`fair3/engine/regime/pipeline.py`) that loads Parquet panels or synthesises deterministic data when inputs are missing.
- CLI gains `--clean-root`, `--thresholds`, `--seed`, `--output-dir`, `--dry-run`, `--trace`; metrics are emitted via `record_metrics`.
- `apply_hysteresis` now enforces streak parameters in addition to dwell/cool-down to avoid flip-flops.

## Testing & Tooling
- Unit tests cover the new committee outputs, macro sensitivity, hysteresis streaks, pipeline artefact generation, and CLI wiring.
- Property tests ensure cooldown enforcement with the new streak parameters.
- Documentation (README, docs/VALIDATE.md, docs/roadmap.md, `fair3/engine/regime/README.md`) outlines the new workflow and knobs.


# PR-21 Plan (Execution & Tax IT v2)

## Scope
- Upgrade lot sizing to deterministic integer lots (`size_orders`) while retaining
  `target_to_lots` for backwards compatibility.
- Introduce aggregated Almgren–Chriss costs via `almgren_chriss_cost` and expose
  FIFO/LIFO/min_tax tax matching with four-year loss carry (`MinusBag`).
- Extend the CLI with `--tax-method` and document the richer execution pipeline.

## Design Notes
- Ensure `size_orders` validates shapes, handles zero/negative prices or lot sizes
  gracefully, and mirrors the Δw → lots formula used downstream.
- Implement `compute_tax_penalty` around DataFrame inputs so the future controller
  can plug instrument inventories directly; encapsulate minus management in
  `MinusBag` for reuse.
- Keep `tax_penalty_it` as a lightweight wrapper for quick heuristics while new
  dataclasses (`TaxRules`, `TaxComputation`) surface rich audit information.

## Testing & Tooling
- Extend `tests/unit/test_execution_primitives.py` to cover `size_orders` and the
  scalar Almgren–Chriss helper and guard the alias behaviour.
- Add dedicated tests for `compute_tax_penalty` covering FIFO/LIFO/min_tax, minus
  bag consumption, new-loss capture, and insufficient inventory errors.
- Refresh documentation (README, docs/FAIR-III.md, docs/roadmap.md,
  `fair3/engine/execution/README.md`) and update the plan/CHANGELOG to mark
  PR-21 as complete.


# PR-22 Plan (Mapping v2)

## Scope
- Extend beta estimation with sign priors, CI80-driven weight capping, and
  per-factor tracking-error governance to stabilise instrument allocations.
- Surface CLI overrides for per-factor TE caps and beta CI thresholds.
- Persist richer summary diagnostics (beta CI widths, factor deviation maxima)
  for downstream audit steps.

## Design Notes
- Rework `rolling_beta_ridge` to record enforcement metadata and support
  optional priors sourced from `factor_index.long_sign`.
- Add `cap_weights_by_beta_ci` and factor-level `enforce_te_budget` helpers so
  the pipeline can sequentially clip uncertain instruments and re-solve factor
  exposures before portfolio-level TE shrinkage.
- Update `run_mapping_pipeline` to wire the new governance steps, honour CLI
  overrides, and write normalised allocations after ADV clipping.

## Testing & Tooling
- Extend `tests/unit/test_mapping_beta.py` for sign enforcement and the new
  c-beta scaler, plus `tests/unit/test_mapping_te_budget.py` for factor-level
  TE clamps.
- Ensure CLI `fair3 map` accepts `--te-factor-max/--tau-beta` and re-run lint
  + unit suites to guard the deterministic behaviour.
- Refresh README, docs/FAIR-III.md, docs/roadmap.md, and the changelog to mark
  PR-22 as delivered.


# PR-24 Plan (Reporting v2)

## Scope
- Extend the reporting module with fan charts for wealth and key risk metrics,
  acceptance gate evaluation, attribution IC diagnostics, and PDF dashboards.
- Wire the new artefacts into the monthly report CLI and data classes while
  maintaining backwards compatibility for existing callers.

## Design Notes
- Reuse the bootstrap draws generated for the wealth fan chart to compute
  Sharpe, MaxDD, CVaR, EDaR, and CAGR trajectories; persist quantile bands as
  PNG charts.
- Introduce `acceptance_gates` and `attribution_ic` helpers so reporting and the
  robustness lab share governance logic; emit the acceptance summary as JSON and
  expose IC diagnostics for downstream QA.
- Generate a compact PDF (`reportlab`) combining metrics, compliance flags,
  acceptance gates, and chart artefacts; enrich `MonthlyReportArtifacts` with
  the new paths.

## Testing & Tooling
- Extend unit tests to cover the new artefacts (metric fan charts, acceptance
  JSON, PDF generation) and verify deterministic bootstrap paths.
- Add dedicated coverage for `acceptance_gates`, `attribution_ic`, and
  `plot_fanchart` error paths.
- Update README, module docs, and CHANGELOG to describe the expanded reporting
  workflow and CLI output.


# PR-27 Plan (FRED ingest extension)

## Scope
- Expand the FRED fetcher defaults to cover Treasury constant maturities (1Y-30Y),
  3M Treasury Bills, CPI headline, 5Y/10Y breakeven inflation, and 5Y/10Y TIPS real yields.
- Ensure the fetcher supports both JSON and ZIP CSV payloads for all defaults with
  deterministic parsing, NaN handling for ``."`` placeholders, and start-date filtering.
- Refresh ingest documentation, data source catalogues, and changelog notes to reflect
  the richer default coverage for macro features.

## Design Notes
- Keep credential validation unchanged but surface the extended ``DEFAULT_SYMBOLS`` tuple
  for reuse by CLI callers and documentation. The tuple order mirrors curve tenors to
  preserve audit readability.
- Reuse the existing ZIP parsing logic and reinforce unit coverage to guard the default
  symbol set, default-run behaviour, and metadata bookkeeping.
- Update ingest docs to list the default series explicitly so operators know which
  macro drivers they obtain out-of-the-box when running ``fair3 ingest --source fred``.

## Testing & Tooling
- Add unit tests that assert the expected default tuple and simulate a default fetch run
  via monkeypatched downloads, verifying symbol coverage, metadata length, and dtype
  normalisation.
- Re-run ``ruff``, ``black``, and ``pytest`` and ensure offline fixtures still exercise the
  ZIP parsing path for CSV exports.
