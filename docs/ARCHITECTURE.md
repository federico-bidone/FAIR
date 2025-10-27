# FAIR-III Architecture

This document will describe the layered design of the FAIR-III engine across ingest, ETL, factor modelling, estimation, allocation, mapping, regime overlay, execution, reporting, robustness, and goal-planning components. Detailed content will be added as the implementation progresses through the planned milestones.

## Factor Layer (PR-05)
- `FactorLibrary` genera gli 8–10 macro-premia deterministici partendo dal pannello
  clean, applicando spread quantili coerenti con i segni economici e seed centrali.
- `enforce_orthogonality` fonde fattori altamente correlati e salva loadings PCA per
  audit e governance delle soglie di condizionamento (`tau.delta_rho`).
- Il pipeline orchestrator (`run_factor_pipeline`) scrive `factors.parquet`,
  `factors_orthogonal.parquet`, metadata JSON e, opzionalmente, `validation.csv` (CP-CV,
  DSR, White RC, FDR). `fair3 factors` richiama il pipeline e registra snapshot seed/config.

## Estimation Layer (Σ Engine – PR-06)
- Shrinkage estimators (Ledoit–Wolf, graphical lasso via BIC, factor shrinkage)
  produce candidate covariances on the clean return panel.
- Element-wise median aggregation and Higham projection maintain PSD.
- EWMA blending links consecutive estimates to respect drift tolerances from
  `configs/thresholds.yml`.
- Drift diagnostics feed execution/no-trade logic and acceptance gates.
- `run_estimate_pipeline` orchestri μ/Σ (ensemble + BL fallback) e persiste
  `mu_post.csv`, `sigma.npy`, `blend_log.csv`, aggiornando `risk/sigma_drift_log.csv` e
  l'audit trail (`fair3 estimate`).

## Optimisation Layer (PR-08)
- I generatori A–D rispettano vincoli ERC cluster, CVaR/EDaR, turnover e DRO e forniscono
  baseline HRP.
- Il meta-learner combina al più tre generatori penalizzando turnover e tracking-error,
  producendo pesi non negativi che sommano a 1.
- `run_optimization_pipeline` salva i pesi di ciascun generatore, l'allocazione finale,
  diagnostiche RC e, se attivo, `meta_weights.csv`. Il comando `fair3 optimize` cura anche
  la registrazione degli audit snapshot.

## Mapping Layer (PR-09)
- Rolling ridge regressions translate factor portfolios into instrument betas with
  optional sign governance and metadata for downstream audits.
- Bootstrap CI80 bands flag noisy exposures so downstream steps can cap or drop
  instruments when `beta_CI_width` breaches thresholds.
- Intra-cluster HRP assigns equal budgets per factor label before redistributing
  within clusters to maintain diversification.
- Tracking-error and ADV guards shrink weights toward baselines and scale trades
  to remain within UCITS liquidity tolerances.
- `run_mapping_pipeline` (CLI: `fair3 map`) allinea fattori/strumenti, calcola betas,
  CI, pesa strumenti con baseline HRP opzionale, applica TE/ADV caps e aggiorna l'audit.

## Regime Layer (PR-10)
- Deterministic committee blends a two-state Gaussian HMM over market returns,
  volatility stress indicators, and macro slowdown scores into a crisis
  probability.
- Hysteresis logic enforces `on > off` thresholds, dwell periods, and cooldown
  windows to avoid flip-flopping between regimes.
- Tilt mapping converts probabilities into blend weights for crisis-aware
  allocations consumed by the execution layer.

## Execution Layer (PR-11)
- Lot sizing converts weight deltas into integer orders using prices and lot
  minimums, ensuring zero-priced instruments do not generate spurious trades.
- Transaction cost model blends explicit fees, half-spread slippage, and ADV
  based impact calibrated to Almgren–Chriss style curves.
- Italian tax heuristic distinguishes govies (12.5%) from other assets (26%),
  applies a rolling loss bucket, and adds 0.2% stamp duty on positive balances.
- Drift/turnover gates combine EB_LB − COST − TAX > 0 with tolerance bands on
  weights and risk contributions to prevent unnecessary churn.
- Decision summaries feed CLI dry-runs and audit artefacts under
  `artifacts/costs_tax/` and `artifacts/trades/`.

## Reporting Layer (PR-12)
- `MonthlyReportInputs` packages PIT artefacts (returns, weights, factor &
  instrument attribution, turnover, costs, taxes, compliance flags).
- `compute_monthly_metrics`/`generate_monthly_report` emit deterministic
  CSV/JSON outputs plus plots (`fan_chart.png`, `attribution.png`,
  `turnover_costs.png`) inside `artifacts/reports/<period>/`.
- Plot helpers rely on the Agg backend for CI compatibility and close figures
  after saving to avoid memory leaks.
- ERC cluster summaries roll up weights per cluster to verify the acceptance
  tolerance `tau.rc_tol` downstream.
- The CLI wrapper currently seeds synthetic fixtures so audit/test infrastructure
  can validate the reporting contract until the full pipeline wiring lands.

## Robustness Layer (PR-13)
- `run_robustness_lab` orchestrates block bootstraps, shock replays, and ablation
  toggles, persisting artefacts under `artifacts/robustness/` alongside a JSON
  gate summary for CI assertions.
- Bootstraps rely on 60-day overlapping blocks with the dedicated `robustness`
  RNG stream so repeated runs in CI/Windows reproduce identical distributions.
- Scenario replays scale stylised crises (1973 oil, 2008 GFC, 2020 COVID, 1970s
  stagflation) to the observed volatility, surfacing worst-case drawdowns for
  governance review.
- The ablation harness expects a callback that re-runs downstream pipeline
  components with specific governance flags toggled off, logging metric deltas
  (e.g., Sharpe, drawdown, TE) to demonstrate each guardrail's contribution.

## Goals Layer (PR-14)
- `simulate_goals` samples Bernoulli regime states (base vs crisis) per month
  using synthetic curves seeded via `SeedSequence`, producing final-wealth
  distributions for each configured household goal.
- Contribution schedules grow at a configurable annual rate while glidepaths
  linearly shift allocation from growth to defensive assets over the maximum
  horizon.
- `run_goal_monte_carlo` scrive `goals_<investor>_summary.csv`,
  `goals_<investor>_glidepaths.csv`, `goals_<investor>_fan_chart.csv` e un
  PDF `goals_<investor>.pdf` sotto `reports/` (o root custom) così CI e auditor
  possono verificare probabilità, fan-chart e glidepath adattivo.
- CLI wiring (`fair3 goals`) loads `configs/goals.yml`/`configs/params.yml`,
  applies optional overrides, and prints weighted success probabilities for
  quick feedback during tuning.
