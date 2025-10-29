# Modulo di reporting

Il pacchetto di reporting aggrega i risultati prodotti dal motore di portafoglio. In
oltre agli assistenti di audit introdotti in precedenza, ora espone un generatore di report
mensile con utilità di grafico deterministico per soddisfare i requisiti di divulgazione al dettaglio di FAIR-III
.

## API pubbliche

### `fair3.engine.reporting.audit`
- `ensure_audit_dir(audit_dir=None)`
- `copy_seed_snapshot(seed_path="audit/seeds.yml", audit_dir=None, timestamp=None)`
- `snapshot_configs(config_paths, audit_dir=None, timestamp=None)`
- `record_checksums(targets, audit_dir=None, timestamp=None)`
- `append_change_log(message, audit_dir=None, timestamp=None)`
- `run_audit_snapshot(seed_path=..., config_paths=(), checksums=None, note=None, audit_dir=None, timestamp=None)`

### `fair3.engine.reporting.monthly`
- `MonthlyReportInputs`
- `MonthlyReportArtifacts`
- `compute_monthly_metrics(returns)`
- `generate_monthly_report(inputs, period_label, output_dir=None, seed=0)`
- `simulate_fan_chart(returns, seed, paths=256, return_paths=False)`
- `acceptance_gates(metrics, thresholds, alpha_drawdown=None, alpha_cagr=None)`
- `attribution_ic(weights, returns, factors, window=12)`

### `fair3.engine.reporting.plots`
- `plot_fan_chart(wealth_paths, percentiles=(0.05, 0.5, 0.95), path=None)`
- `plot_fanchart(axis, dates, median, lower, upper, title=None, ylabel=None)`
- `plot_attribution(contributions, path=None, stacked=True)`
- `plot_turnover_costs(turnover, costs, path=None)`

## CLI/Utilizzo pipeline

All'interno del comando `fair3 report --period YYYY-MM:YYYY-MM --monthly` la CLI
carica gli artefatti PIT, assembla la struttura `MonthlyReportInputs` ed emette
CSV/JSON riepiloghi, grafici PNG, diagnostica del gate di accettazione e un PDFistantanea
all'interno `artifacts/reports/<period>/`.L'aiutante accetta un `output_dir`
 personalizzato per facilitare test di regressione e quaderni.

```python
from fair3.engine.reporting import MonthlyReportInputs, generate_monthly_report

artifacts = generate_monthly_report(
    MonthlyReportInputs(
        returns=returns_series,
        weights=weights_df,
        factor_contributions=factor_attr,
        instrument_contributions=instrument_attr,
        turnover=turnover_series,
        costs=cost_series,
        taxes=tax_series,
        compliance_flags={"ucits": True, "no_trade": True},
        instrument_returns=instrument_returns,
        factor_returns=factor_returns,
        bootstrap_metrics=bootstrap_metrics,
        thresholds={"max_drawdown_threshold": -0.25, "cagr_target": 0.03},
    ),
    period_label="2025-01:2025-06",
    seed=42,
)
print("Metrics saved to", artifacts.metrics_csv)
print("Acceptance gates", artifacts.acceptance_json)
print("Monthly PDF", artifacts.report_pdf)
```

## Errori comuni e risoluzione dei problemi

| Sintomo | Probabile causa | Risoluzione |
| --- | --- | --- |
| Output PNG mancanti | Backend Matplotlib non impostato in CI headless | Il modulo forza `Agg`, garantisce la dipendenza installata |
| Cornici di aggregazione vuote | L'ETL upstream non ha popolato gli artefatti PIT | Verificare la fase ETL e i filtri della data prima di eseguire i report |
| Date non monotone | Le fusioni a monte hanno prodotto indici non ordinati | Chiama `.sort_index()` prima di inserire gli input del report |

## Trace Hooks

Gli aiutanti di audit e il generatore mensile rispondono al flag globale `--trace`
riutilizzando il logger configurato tramite `fair3.engine.logging.setup_logger`.Includi
percorsi degli artefatti nei log di traccia per una diagnosi rapida.
