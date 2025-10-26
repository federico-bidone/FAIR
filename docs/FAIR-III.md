# FAIR-III Methodology

## Macro Factors Stack (PR-05)
The FAIR-III factor engine synthesises ten macro premia, blending cross-sectional long/short spreads and macro overlays. Each factor is anchored to an expected economic sign and built off the point-in-time panel generated in PR-04.

- **Global Market (`global_mkt`)** – equal-weight beta proxy.
- **Global Momentum / Growth Cycle** – high-minus-low trailing log returns and improving short-term momentum captures.
- **Short-Term Reversal / Value Rebound** – contrarian tilts exploiting lagged underperformance.
- **Carry Roll-Down** – 5d–21d momentum spread as a roll premium proxy.
- **Quality & Defensive Stability** – low-volatility and momentum-per-unit-risk exposures.
- **Liquidity Risk** – high-minus-low volatility cohort spread.
- **Inflation Hedge / Rates Beta** – macro overlays driven by inflation and policy-rate surprises (fallback to zeros when macro data absent).

Each factor series è generata deterministicamente via `FactorLibrary` e salvata da
`run_factor_pipeline` (`fair3 factors`) che registra anche metadata (`FactorDefinition.expected_sign`)
e diagnostiche CP-CV/FDR per audit e compliance.

### Validation & Controls
- **Cross-Purged CV (CP-CV)** with embargo ensures no look-ahead in factor testing.
- **Deflated Sharpe Ratio (DSR)** quantifies statistical significance of Sharpe estimates.
- **White Reality Check (permutation bootstrap)** guards against data mining, with FDR Benjamini–Hochberg filtering to control false discoveries across the library.
- **Orthogonality Guardrails** merge highly correlated factors (|ρ| > τ) and apply PCA rotation when the correlation matrix condition number exceeds the tolerance in `configs/thresholds.yml`.

## Expected-Returns Engine (PR-07)
The μ stack follows a deterministic ensemble design:

- **Shrink-to-zero baseline:** sample means shrinked towards 0 with intensity
  tied to T/N, ensuring stability when history is short.
- **Bagging OLS:** bootstrapped linear models on lagged macro + return features
  provide low-variance conditional forecasts.
- **Gradient boosting:** shallow trees with early stopping capture light
  nonlinearities without sacrificing reproducibility.
- **Ridge stacking:** non-negative ridge regression combines the base learners,
  using time-series cross-validation folds to calibrate the mix.
- **Black–Litterman blend:** `reverse_opt_mu_eq` infers equilibrium returns from
  Σ and market weights; `blend_mu` enforces the ω:=1 fallback whenever the view
  information ratio breaches `tau.IR_view` in `configs/thresholds.yml`.

`run_estimate_pipeline` (`fair3 estimate`) persiste `mu_post.csv`, `mu_star.csv`,
`mu_eq.csv`, `sigma.npy` e `blend_log.csv` con ω e IR_view per audit trail, oltre a
`risk/sigma_drift_log.csv` quando confronta stime consecutive.

## Covariance Engine (PR-06)
The covariance stack combines multiple estimators to maintain PSD structure and
monitor structural drift:

- **Ledoit–Wolf shrinkage** towards the identity baseline.
- **Graphical lasso** with BIC model selection to promote sparse precision
  matrices.
- **Factor shrinkage** from leading eigenvectors plus positive idiosyncratic
  noise.
- **Element-wise median** aggregation followed by **Higham PSD projection**.
- **Geometric SPD median** optional consensus (`--sigma-engine spd_median`) computed
  via affine-invariant gradient descent with Higham fallback on non-convergence.
- **EWMA regime blending** with configurable `lambda_r` to smooth transitions
  while enforcing PSD at every step.
- **Drift diagnostics** (`frobenius_relative_drift`, `max_corr_drift`) feed the
  acceptance gates in `configs/thresholds.yml`.

Gli artefatti sono scritti direttamente in `artifacts/estimates/` e accompagnati
da snapshot seed/config attraverso `reporting.audit`.

## Allocation Stack (PR-08)
The allocation layer introduces four deterministic generators plus a meta-learner:

- **Generator A (Sharpe + constraints):** solves a convex programme that maximises expected return penalised by a Wasserstein DRO radius, while enforcing long-only weights, turnover/gross leverage caps, and scenario-based CVaR95/EDaR risk limits. ERC cluster balancing is applied post-solve to honour tolerance `tau.rc_tol`.
- **Generator B (HRP):** classical hierarchical risk parity baseline using Ward linkage and quasi-diagonalisation, serving as the retail benchmark and acceptance-gate reference.
- **Generator C (DRO closed form):** ridge-regularised inverse of Σ scaled by risk aversion `γ` and penalty `ρ`, yielding a fast fallback when solver resources are constrained.
- **Generator D (CVaR-ERC):** minimises scenario CVaR subject to turnover/leverage caps and ERC cluster balancing for tail-risk sensitive allocations.
- **Meta learner:** fits non-negative simplex weights over generator PnLs with quadratic risk penalty and turnover/TE penalties relative to a baseline generator (default HRP).

Il pipeline `run_optimization_pipeline` (`fair3 optimize`) genera CSV per ciascun
motore, l'allocazione finale, diagnostiche ERC e, se richiesto, `meta_weights.csv`,
registrando audit snapshot e checksum.

## Mapping & Liquidity (PR-09)
The mapping layer translates factor weights into implementable instruments while
respecting UCITS liquidity guardrails:

- **Rolling ridge betas:** `rolling_beta_ridge` centres each window, applies
  ridge parameter `lambda_beta`, and stores estimator metadata for downstream
  bootstrap diagnostics. Optional sign constraints enforce economic priors.
- **Bootstrap confidence intervals:** `beta_ci_bootstrap` resamples windows with
  deterministic RNG streams to compute CI80 ranges used to cap noisy betas when
  `width > tau.beta_CI_width`.
- **CI-driven caps:** `cap_weights_by_beta_ci` scales instrument weights when
  CI80 widths breach `tau.beta_CI_width`, preserving the budget after
  renormalisation.
- **Intra-factor HRP:** `hrp_weights` splits instrument clusters by factor label
  and assigns equal cluster budgets before running HRP within each group.
- **Tracking-error budgets:** `enforce_te_budget` clamps factor deviations to
  `TE_max_factor`, while `enforce_portfolio_te_budget` shrinks mapped weights
  toward a baseline (e.g., HRP) to satisfy the same tolerance.
- **ADV caps:** `clip_trades_to_adv` converts proposed trade weights into
  notional terms and rescales them to obey ADV percentage limits while
  preserving trade direction.

`run_mapping_pipeline` (`fair3 map`) scrive i rolling betas, le CI80, il riassunto di
tracking-error e `weights/instrument_allocation.csv`, aggiornando i log di audit per
beta, TE e clip ADV prima dell'esecuzione.

## Regime Overlay (PR-10)
The regime layer guards allocations with a deterministic crisis-probability
committee and hysteresis controls:

- **Committee signals:** equal-weight market returns feed a fixed two-state
  Gaussian HMM, volatility stress is derived from rolling-median normalised
  volatility ratios, and macro slowdown scores come from standardised deltas of
  macro indicators. Component weights default to (0.5, 0.3, 0.2) and are
  normalised for auditability.
- **Probability governance:** outputs are clipped to \[0, 1\] and logged for
  downstream acceptance gates. Missing inputs revert to neutral priors to keep
  the overlay deterministic.
- **Hysteresis + dwell:** `apply_hysteresis` enforces on/off thresholds (default
  on=0.65, off=0.45), minimum dwell (20 trading days), and cooldown (10 days)
  before re-entry. This prevents rapid flip-flops during choppy markets.
- **Tilt mapping:** `tilt_lambda` linearly maps crisis probabilities to tilt
  weights in \[0, 1\], blending baseline and crisis allocations in execution.

The overlay will surface logs and component diagnostics in
`artifacts/audit/regime/` when the CLI wiring lands, ensuring reproducible audit
trails for compliance checks.

## Execution Layer (PR-11)
The execution layer enforces the retail guardrails before any order is routed:

- **Lot sizing:** `size_orders` converts weight deltas into integer lots using
  portfolio value, prices, and lot sizes; `target_to_lots` remains available as a
  thin alias for backwards compatibility.
- **Transaction costs:** `trading_costs` implements the Almgren–Chriss schema –
  explicit fees, half-spread slippage, and nonlinear market impact scaled by the
  ADV percentage – while `almgren_chriss_cost` exposes the aggregated impact for
  CLI summaries.
- **Taxes:** `compute_tax_penalty` applies the Italian regime (26% default,
  12.5% for govies ≥51%, 0.2% bollo) with FIFO/LIFO/min_tax matching and a
  four-year `MinusBag` loss carry; `tax_penalty_it` remains as a quick
  aggregated heuristic.
- **No-trade guard:** `drift_bands_exceeded` checks weight and risk contribution
  drift against tolerance bands; `expected_benefit_distribution` and
  `expected_benefit_lower_bound` estimate EB_LB via block bootstrap before
  `should_trade` combines drift, turnover caps, and the EB_LB − COST − TAX > 0
  acceptance gate.
- **Decision summaries:** `DecisionBreakdown` structures the gate evaluation for
  CLI dry-runs and audit logging ahead of the full controller landing in PR-12.

Outputs will populate `artifacts/trades/` and `artifacts/costs_tax/` alongside
audit snapshots to maintain reproducibility.

## Reporting & Monthly Disclosures (PR-12)
The reporting layer transforms PIT artefacts into retail-friendly disclosures:

- **Metrics deck:** `compute_monthly_metrics` annualises returns, calculates
  Sharpe, Max Drawdown, CVaR(95), and three-year EDaR using deterministic
  rounding (4 d.p.). Results are emitted as both CSV and JSON for auditability.
- **Attribution:** Factor and instrument contributions are aggregated monthly
  and exported side-by-side with stacked bar plots for visual inspection.
- **Fan charts:** `simulate_fan_chart` bootstraps wealth and return paths via
  `numpy.random.default_rng(seed)`; `plot_fan_chart`/`plot_fanchart` render
  deterministic PNG outputs for wealth and risk metrics under
  `artifacts/reports/<period>/`.
- **Turnover & costs:** Monthly turnover, cost, and tax series feed line/bar
  combos to surface compliance with turnover and TE budgets.
- **ERC clusters:** Optional cluster maps roll up average monthly weights,
  supporting acceptance gates on cluster risk parity tolerances.
- **Compliance log:** Flags such as UCITS eligibility, audit completion, and
  no-trade adherence are persisted in `compliance.json` for downstream checks.
- **Acceptance gates:** `acceptance_gates` evaluates P(MaxDD > τ) and the CAGR
  lower bound, emitting `acceptance.json` with pass/fail verdicts.
- **Attribution IC:** `attribution_ic` computes instrument contributions,
  factor contributions, and rolling IC metrics, optionally persisted as CSV for
  governance reviews.
- **PDF dashboard:** `generate_monthly_report` assembles metrics, compliance
  flags, acceptance gates, and chart artefacts into a compact PDF using
  `reportlab`.

The CLI wrapper (`fair3 report --period ... --monthly`) currently feeds the
report generator with deterministic synthetic data so acceptance gates and CI
remain green while upstream orchestration is wired in. Future PRs will swap the
synthetic stub for real PIT artefacts once the end-to-end pipeline is complete.

## Robustness Lab & Ablation (PR-13)
The robustness laboratory extends FAIR-III governance with deterministic stress tests:

- **Block bootstrap:** `block_bootstrap_metrics` samples 60-day blocks (default 1000 draws) to
  compute distributions of max drawdown, CAGR, Sharpe, CVaR, and EDaR. Acceptance gates enforce
  P(MaxDD ≤ τ) ≥ 95% and the 5th-percentile CAGR ≥ target. All runs use the
  `robustness` RNG stream so they are reproducible across CI and research
  environments.
- **Shock replay:** `replay_shocks` replays stylised crisis profiles (1973 oil,
  2008 GFC, 2020 COVID, 1970s stagflation) scaled to the realised volatility of
  the input returns, highlighting worst-case drawdowns for governance reviews.
- **Ablation harness:** `run_ablation_study` toggles governance switches (BL
  fallback, Σ PSD projection, drift trigger, meta TO/TE penalties, regime tilt,
  no-trade rule) to quantify their lift on key metrics. The orchestrator supplies
  a callback that re-runs the downstream pipeline with the provided flags.
- **Artefacts:** `run_robustness_lab` consolidates bootstrap draws, scenarios,
  ablation tables, and a compact PDF summary inside `artifacts/robustness/` and
  persists a JSON summary with gate verdicts for CI assertions.

These diagnostics back the FAIR acceptance gates before monthly reports are
released, ensuring retail guardrails remain active even under structural breaks.

## Goal Planning & Glidepath (PR-14)
Household goals extend FAIR-III beyond portfolio construction, providing a
deterministic Monte Carlo engine for probability-of-success analysis:

- **Regime-aware sampling:** `simulate_goals` draws Bernoulli states between
  base and crisis regimes per month, with curve parameters generated via
  `SeedSequence` so runs remain identical given the same seed.
- **Contribution policy:** `build_contribution_schedule` grows monthly
  contributions at a configurable annual rate (default 2%), ensuring long-horizon
  savings plans reflect inflation drift.
- **Glidepath:** `build_glidepath` linearly transitions allocation from growth
  heavy to defensive weights over the maximum horizon across configured goals,
  surfacing the implied asset mix for governance review.
- **Outputs:** `run_goal_monte_carlo` writes deterministic `goals_<investor>_summary.csv`,
  `goals_<investor>_glidepaths.csv`, `goals_<investor>_fan_chart.csv`, e `goals_<investor>.pdf`
  sotto `reports/` (o root custom);
  il comando CLI `fair3 goals --simulate` stampa le probabilità ponderate e i
  percorsi dei file generati così l'utente può iterare rapidamente su contributi
  e orizzonti.

Acceptance thresholds derive from `configs/goals.yml` (target wealth `W`,
minimum probability `p_min`, weights) and `configs/params.yml` (household
contribution assumptions). Weighted probabilities must meet the specified
`p_min` values to satisfy the FAIR-III goal governance gate.
