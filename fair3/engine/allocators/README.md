# Allocators Module

The allocators package hosts the FAIR-III portfolio construction engines. Each generator respects the retail implementability constraints (long-only, turnover/TE/ADV caps) while enabling risk-aware combinations of factor or instrument returns.

## Public APIs

| Function | Description |
| --- | --- |
| `risk_contributions(w, Sigma)` | Marginal risk contributions \(RC_i = w_i (\Sigma w)_i\). |
| `balance_clusters(w, Sigma, clusters, tol)` | Iteratively rescales cluster weights until ERC deviation is within `tol`. |
| `generator_A(mu, Sigma, constraints)` | Maximise Sharpe with Wasserstein DRO penalty, CVaR/EDaR caps, turnover and leverage constraints, then balance ERC clusters. |
| `generator_B_hrp(Sigma)` | Hierarchical Risk Parity baseline (Ward linkage, quasi-diagonalisation). |
| `generator_C_dro_closed(mu, Sigma, gamma, rho)` | Closed-form distributionally robust portfolio via ridge-regularised inverse. |
| `generator_D_cvar_erc(mu, Sigma, constraints)` | CVaR-minimising allocation with ERC cluster balancing and leverage/turnover caps. |
| `fit_meta_weights(returns_by_gen, sigma_matrix, j_max, penalty_to, penalty_te, baseline_idx)` | Meta-learner that blends generator PnLs with turnover/TE penalties on the simplex. |
| `run_optimization_pipeline(...)` | Wrapper che esegue generatori, meta-learner opzionale e persiste artefatti/audit (`OptimizePipelineResult`). |

## CLI / Integration

`fair3 optimize --generators A,B,C --meta` invoca il pipeline orchestrator e produce:

- `artifacts/weights/generator_*.csv` (pesi per singolo generatore)
- `artifacts/weights/factor_allocation.csv` (allocazione finale)
- `artifacts/weights/allocation_diagnostics.csv` (RC per fattore)
- `artifacts/weights/meta_weights.csv` se `--meta`

Audit snapshot e checksum sono registrati automaticamente.

## Determinism & Seeds

All solvers are deterministic when fed deterministic inputs. Scenario draws must originate from `utils.rand.generator_from_seed`. Solver randomness is disabled by the convex back-ends (SCS/ECOS).

## Common Errors

- **Infeasible CVaR constraints:** ensure `constraints["scenario_returns"]` has adequate history; loosen `cvar_cap` slightly or supply more scenarios.
- **Turnover violation after ERC balancing:** the generator shrinks the post-balancing move if turnover exceeds the cap. Provide realistic `turnover_cap` (>0.01) to avoid degeneracy.
- **HRP single asset edge cases:** the HRP generator returns `[1.0]` when only one asset is present.

## Tracing Flags

Pass `constraints["trace"] = True` to receive solver status messages and cluster diagnostics in the allocator log file.
