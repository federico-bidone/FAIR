# Execution Module

The execution layer transforms mapped factor deltas into implementable orders
while enforcing UCITS retail guardrails. It exposes deterministic primitives
that upstream orchestration stitches together when the portfolio is ready to
trade.

## Public APIs

- `target_to_lots(delta_w, portfolio_value, prices, lot_sizes)` – convert target weight
  changes into integer lot counts while respecting zero-priced or ill-defined
  instruments.
- `trading_costs(prices, spreads, q, fees, adv, eta)` – Almgren–Chriss cost
  model combining explicit fees, half-spread slippage, and nonlinear market
  impact scaled by ADV.
- `tax_penalty_it(realized_pnl, govies_ratio, stamp_duty_rate)` – simplified
  Italian tax heuristic (26% default, 12.5% for qualifying govies, 0.2% bollo).
- `drift_bands_exceeded(w_old, w_new, rc_old, rc_new, band)` – signal whether
  weight or risk contribution drift breaches no-trade tolerances.
- `expected_benefit(delta_w, mu, Sigma, w_old, w_new)` – lower bound for the
  execution expected benefit used in the EB_LB gate.
- `should_trade(drift_ok, eb_lb, cost, tax, turnover_ok)` – deterministic gate
  implementing `EB_LB − COST − TAX > 0` with drift/turnover checks.
- `summarise_decision(...)` – returns a `DecisionBreakdown` dataclass handy for
  CLI dry-runs and logging.

All functions are vectorised via NumPy and expect consistent shapes. Raise
`ValueError` for mismatched dimensions to keep orchestration failures explicit.

## CLI / Python Usage

```python
from fair3.engine.execution import (
    DecisionBreakdown,
    drift_bands_exceeded,
    expected_benefit,
    should_trade,
    summarise_decision,
    target_to_lots,
    tax_penalty_it,
    trading_costs,
)

lots = target_to_lots(delta_w, portfolio_value=1_000_000, prices=prices, lot_sizes=lot_sizes)
costs = trading_costs(prices, spreads, lots * lot_sizes, fees, adv, eta)
tax = tax_penalty_it(realised_pnl, govies_ratio)
drift_ok = drift_bands_exceeded(w_old, w_new, rc_old, rc_new, band=0.02)
eb = expected_benefit(delta_w, mu_instr, Sigma_instr, w_old, w_new)
decision = summarise_decision(drift_ok, eb, costs.sum(), tax, turnover_ok=True)
```

The CLI `fair3 execute` command currently supports `--rebalance-date` and
`--dry-run` to surface these diagnostics; full orchestration will land once the
reporting layer (PR-12) is integrated.

## Tracing & Logs

- Execution logs are written under `artifacts/audit/execution.log` when the
  module is driven via the CLI with `--trace` (to be added alongside orchestration).
- Lot sizing, costs, and tax estimates should be snapshot to
  `artifacts/trades/` and `artifacts/costs_tax/` by the controller.

## Common Errors

- **Shape mismatch:** ensure prices, spreads, quantities, and lot sizes share the
  same length.
- **Zero ADV:** the helper gracefully treats zero ADV as no additional market
  impact but still logs the instrument for manual inspection.
- **Drift bands too tight:** if `band` is smaller than numerical noise, expect
  frequent rebalancing; adjust via `configs/params.yml`.
