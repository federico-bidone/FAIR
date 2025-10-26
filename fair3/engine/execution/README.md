# Execution Module

The execution layer transforms mapped factor deltas into implementable orders
while enforcing UCITS retail guardrails. It exposes deterministic primitives
that upstream orchestration stitches together when the portfolio is ready to
trade.

## Public APIs

- `size_orders(delta_w, portfolio_value, prices, lot_sizes)` – convert weight
  changes into integer lot counts; alias `target_to_lots` is kept for
  compatibility.
- `trading_costs(prices, spreads, q, fees, adv, eta)` – Almgren–Chriss cost
  model combining explicit fees, half-spread slippage, and nonlinear market
  impact scaled by ADV.
- `almgren_chriss_cost(order_qty, price, spread, adv, eta, fees)` – scalar
  wrapper returning the aggregate Almgren–Chriss cost useful for CLI summaries.
- `compute_tax_penalty(orders, inventory, tax_rules)` – Italian tax engine with
  FIFO/LIFO/min_tax matching, four-year loss carry, and bollo; `tax_penalty_it`
  remains available for quick aggregated estimates.
- `drift_bands_exceeded(w_old, w_new, rc_old, rc_new, band)` – signal whether
  weight or risk contribution drift breaches no-trade tolerances.
- `expected_benefit(delta_w, mu, Sigma, w_old, w_new)` – analytic lower bound for
  the execution expected benefit used per bootstrap sample.
- `expected_benefit_distribution(returns, delta_w, w_old, w_new, block_size,
  n_resamples, seed)` – block bootstrap distribution of expected benefit values.
- `expected_benefit_lower_bound(returns, delta_w, w_old, w_new, alpha, block_size,
  n_resamples, seed)` – EB_LB computed as the ``alpha``-quantile of the bootstrap
  distribution.
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
    MinusBag,
    TaxRules,
    almgren_chriss_cost,
    compute_tax_penalty,
    drift_bands_exceeded,
    expected_benefit_distribution,
    expected_benefit_lower_bound,
    should_trade,
    size_orders,
    summarise_decision,
    tax_penalty_it,
    trading_costs,
)

current_value = 1_000_000
lots = size_orders(delta_w, portfolio_value=current_value, prices=prices, lot_sizes=lot_sizes)
costs = trading_costs(prices, spreads, lots * lot_sizes, fees, adv, eta)
total_cost = almgren_chriss_cost(lots * lot_sizes, prices, spreads, adv, eta, fees=fees)
order_frame = make_orders_dataframe(...)
inventory_frame = make_inventory_dataframe(...)
tax_rules = TaxRules(method="fifo", portfolio_value=current_value, minus_bag=MinusBag())
tax = compute_tax_penalty(order_frame, inventory_frame, tax_rules)
drift_ok = drift_bands_exceeded(w_old, w_new, rc_old, rc_new, band=0.02)
distribution = expected_benefit_distribution(returns, delta_w, w_old, w_new, block_size=60, n_resamples=256, seed=42)
eb_lb = expected_benefit_lower_bound(returns, delta_w, w_old, w_new, alpha=0.05, block_size=60, n_resamples=256, seed=42)
decision = summarise_decision(drift_ok, eb_lb, total_cost, tax.total_tax, turnover_ok=True)
```

The CLI `fair3 execute` command now accepts `--rebalance-date`, `--tax-method`
(`fifo`, `lifo`, `min_tax`) and `--dry-run` to surface these diagnostics; full
orchestration will land once the reporting layer (PR-12) is integrated.

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
