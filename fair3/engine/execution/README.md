# Modulo di esecuzione

Il livello di esecuzione trasforma i delta dei fattori mappati in ordini implementabili
applicando al contempo i guardrail al dettaglio degli OICVM.Espone le primitive deterministiche
che l'orchestrazione a monte si unisce quando il portafoglio è pronto per essere scambiato
.

## API pubbliche

- `size_orders(delta_w, portfolio_value, prices, lot_sizes)` – converte il peso
  modifiche in conteggi di lotti interi; alias `target_to_lots` viene mantenuto per
  compatibilità.
- `trading_costs(prices, spreads, q, fees, adv, eta)` – Costo Almgren–Chriss
  modello che combina commissioni esplicite, slippage a metà spread e mercato non lineare
  impatto ridimensionato da ADV.
- `almgren_chriss_cost(order_qty, price, spread, adv, eta, fees)` – scalare
  wrapper che restituisce il costo Almgren–Chriss aggregato utile per la CLIsintesi.
- `compute_tax_penalty(orders, inventory, tax_rules)` – Motore fiscale italiano con
  FIFO/LIFO/min_taxmatch, loss carry a quattro anni e bollo; `tax_penalty_it`
  rimane disponibile per stime aggregate rapide.
- `drift_bands_exceeded(w_old, w_new, rc_old, rc_new, band)` – segnala se
  la deriva del peso o del contributo al rischio viola le tolleranze non commerciali.
- `expected_benefit(delta_w, mu, Sigma, w_old, w_new)` – limite inferiore analitico per
  il vantaggio previsto dall'esecuzione utilizzato per campione bootstrap.
- `expected_benefit_distribution(returns, delta_w, w_old, w_new, block_size,
  n_resamples, seed)` – blocca la distribuzione bootstrap dei valori dei benefici attesi.
- `expected_benefit_lower_bound(returns, delta_w, w_old, w_new, alpha, block_size,
  n_resamples, seed)` – EB_LB computed as the ``alpha``-quantile della distribuzione bootstrap
  .
- `should_trade(drift_ok, eb_lb, cost, tax, turnover_ok)` – gate deterministico
  implementazione di `EB_LB − COST − TAX > 0` con controlli di deriva/fatturato.
- `summarise_decision(...)` – restituisce una classe di dati `DecisionBreakdown` a portata di manoper
  CLI prove di prova e logging.

Tutte le funzioni sono vettorizzate tramite NumPy e si aspettano forme coerenti. Aumenta
`ValueError` per le dimensioni non corrispondenti per mantenere espliciti gli errori di orchestrazione.

## Utilizzo CLI/Python

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

Il comando CLI `fair3 execute` ora accetta `--rebalance-date`, `--tax-method`
(`fifo`, `lifo`, `min_tax`) e `--dry-run` per far emergere queste diagnostiche; completo
l'orchestrazione verrà eseguita una volta integrato il livello di reporting (PR-12).

## Tracciamento e registri

- I registri di esecuzione vengono scritti in `artifacts/audit/execution.log` quando il modulo
   viene gestito tramite la CLI con `--trace` (da aggiungere insieme all'orchestrazione).
- Il dimensionamento dei lotti, i costi e le stime fiscali devono essere istantanee su
  `artifacts/trades/` e `artifacts/costs_tax/` dal titolare del trattamento.

## Errori comuni

- **Mancata corrispondenza della forma:** garantisce che prezzi, spread, quantità e dimensioni dei lotti condividano la stessa lunghezza
  .
- **Zero ADV:** l'assistente tratta con garbo zero ADV come nessun mercato aggiuntivo
  ma registra comunque lo strumento per l'esecuzione manualeispezione.
- **Bande di deriva troppo strette:** se `band` è inferiore al rumore numerico, prevedere
  frequenti ribilanciamenti; regolare tramite `configs/params.yml`.
