# Mapping Module

## Purpose
The mapping layer converts factor portfolios into implementable instrument exposures.
It provides deterministic beta estimation, liquidity-aware sizing, and tracking-error
controls before execution.

## Public API
- `rolling_beta_ridge(returns, factors, window, lambda_beta, sign_prior=None,
  enforce_sign=True)` estimates rolling ridge betas under optional economic sign
  constraints.
- `beta_ci_bootstrap(returns, factors, beta_ts, B=1000, alpha=0.2)`
  generates confidence intervals to cap noisy exposures.
- `cap_weights_by_beta_ci(weights, beta_ci, tau_beta)` rescales instrument
  weights when confidence intervals are wide.
- `hrp_weights(Sigma, labels)` computes intra-factor hierarchical risk parity weights.
- `tracking_error(weights, baseline, Sigma)` evaluates TE for factor budgets.
- `enforce_te_budget(exposures, target_exposure, te_factor_max)` clamps factor
  deviations, while `enforce_portfolio_te_budget(weights, baseline, Sigma, cap)`
  shrinks exposures until the portfolio tracking-error cap is met.
- `max_trade_notional(adv, prices, cap_ratio)` derives ADV notional caps.
- `clip_trades_to_adv(delta_w, portfolio_value, adv, prices, cap_ratio)` resizes trades
  to respect ADV thresholds without flipping signs.
- `run_mapping_pipeline(...)` orchestri il mapping fattore→strumento e restituisce
  `MappingPipelineResult` con percorsi per betas, CI e pesi strumentali.

## CLI Hooks
`fair3 map --hrp-intra --adv-cap 0.05` invoca il pipeline orchestrator e produce:

- `artifacts/mapping/rolling_betas.parquet`
- `artifacts/mapping/beta_ci.parquet`
- `artifacts/mapping/summary.json` (TE prima/dopo)
- `artifacts/weights/instrument_allocation.csv`

Le soglie TE/ADV sono lette da `configs/thresholds.yml` e ogni run registra audit snapshot
dei file YAML e dei checksum degli artefatti.

## Trace Flags
The module honours the global logging/trace configuration; set `--trace` on the CLI to
emit beta window diagnostics and TE/liquidity adjustments.

## Common Errors
- Misaligned indices between returns and factors result in `ValueError`.
- Using a window larger than the available history raises an exception.
- Negative ADV caps or portfolio values trigger validation errors.

Logs and bootstrap diagnostics are written under `artifacts/audit/` via the reporting
stack to aid post-trade reviews.
