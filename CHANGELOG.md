# Changelog

## [0.2.0] - 2024-09-18
### Added
- Repository scaffolding for FAIR-III v0.2 roadmap (data lake folders, audit checksum placeholder, refreshed README with
  Quickstart v0.2, CLI reference, UCITS/EU/IT compliance guidance).
- Tooling alignment with Google Python Style Guide: `black` 100-col limit, `ruff` Google docstring checks, pytest pre-commit
  hook, consolidated configuration in `pyproject.toml`.
- Configuration validator CLI (`fair3 validate`) leveraging pydantic schemas with verbose output and
  dedicated unit tests.
- Structured observability primitives: `fair3.engine.logging.setup_logger`, JSON audit mirroring, metrics
  JSONL writer, CLI-wide `--progress/--json-logs` flags, and refreshed docs/tests capturing the new
  workflow.
- Regime Engine v2: `regime_probability`, hysteresis streak controls, CLI `fair3 regime` with artefact
  persistence (`probabilities.csv`, `hysteresis.csv`, `committee_log.csv`), and validation updates for
  committee/macro weights.
- Covariance consensus upgrades: optional SPD geometric median (`sigma_spd_median`), CLI flag
  `--sigma-engine`, PSD/ordering property tests, and refreshed documentation for the estimation
  pipeline.
- Block-bootstrap expected benefit engine: `block_bootstrap`, EB distribution helpers, EB_LB
  monotonicity tests, and documentation updates for execution guardrails.
- Execution & Tax IT v2: `size_orders` lot sizing upgrade, Almgren–Chriss scalar
  helper, Italian tax engine (`compute_tax_penalty`, `MinusBag`) with CLI
  `--tax-method` wiring and refreshed documentation/tests.
- Mapping v2: rolling ridge betas with sign priors, CI80-driven weight caps,
  per-factor tracking-error governance, new CLI overrides (`--te-factor-max`,
  `--tau-beta`), and extended tests/documentation for mapping controls.
- Goal Engine v2: regime-aware Monte Carlo con contributi/riscatti programmati,
  glidepath adattivo, fan-chart mensili, CLI `fair3 goals --simulate`, output in
  `reports/`, e test aggiornati su schedule/glidepath.
- Reporting v2: metric fan charts, acceptance gate evaluation, attribution IC
  diagnostics, PDF summaries, CLI enhancements, and documentation/tests for the
  expanded reporting workflow.
- Mini GUI opzionale: `launch_gui`, comando `fair3 gui` con flag di percorso,
  fallback quando PySide6 manca, documentazione dedicata e test smoke con
  stub/assenza dipendenza.

### Changed
- Bumped package version to `0.2.0` in `pyproject.toml` and exposed the version in `fair3.__init__` for runtime introspection.

### Notes
- Questa release costituisce la base per le PR PR-16 → PR-50 (regime v2, Σ SPD-median, bootstrap v2, execution & tax v2,
  mapping v2, goals v2, reporting v2, ingest multi-fonte, mini GUI).
- Tutti i componenti restano marcati come preview: l'utilizzo è limitato a scopi educativi e di ricerca.
