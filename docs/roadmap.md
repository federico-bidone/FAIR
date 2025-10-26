# FAIR-III v0.2 Roadmap

Questa roadmap segue il piano PR-15 → PR-50 richiesto per la versione FAIR-III v0.2. Ogni blocco elenca
le funzionalità da implementare, i file principali da toccare e i rischi da monitorare.

## PR-15 — Version bump & scaffolding (questa PR)
- Aggiornare `pyproject.toml` e `fair3/__init__.py` a `0.2.0`.
- Preparare `data/raw/`, `data/clean/`, `audit/checksums.json`, Quickstart README e tabella CLI.
- Configurare `black`/`ruff` (docstring Google-style) e hook `pytest` in pre-commit.

## PR-16 — Config validator
- Comando `fair3 validate` con `pydantic`/`jsonschema` e test in `tests/unit/test_validate.py`.
- Nuovo modulo `fair3/engine/validate.py`; documentazione in `docs/VALIDATE.md`.

## PR-17 — Logging & osservabilità
- `fair3/engine/logging.py` con logger strutturato, `record_metrics`, opzione `--json-logs`/`--progress`.
- Aggiornare CLI per usare il logger e scrivere metriche in `artifacts/audit/metrics.jsonl`.

## PR-18 — Regime Engine v2 ✅
- HMM/HSMM (`hmmlearn`), vol-state e macro trigger (inflazione YoY, PMI, tassi reali) con `regime_probability`.
- Isteresi/dwell/cool-down + streak configurabili (`configs/thresholds.yml`), CSV `artifacts/regime/{probabilities,hysteresis,committee_log}.csv`.
- CLI `fair3 regime` con `--clean-root`, `--thresholds`, `--seed`, `--output-dir`, `--dry-run`, `--trace`; test su isteresi e sensibilità macro.

## PR-19 — Σ SPD-median ✅
- Implementare `sigma_spd_median` (Riemannian median) con fallback Higham.
- Flag `--sigma-engine spd_median` nella CLI estimate, property test PSD.

## PR-20 — Bootstrap v2 & EB_LB ✅
- `block_bootstrap` (blocchi 60g) e `eb_lower_bound` centralizzati con seed deterministico e test su momenti.
- Distribuzione EB bootstrap integrata in execution, monotonicità EB_LB verificata da property test.

## PR-21 — Execution & Tax IT v2 ✅
- Lotti discreti (`size_orders` + alias `target_to_lots`), flag CLI `--tax-method`
  (FIFO/LIFO/min_tax), 26% / 12.5% / bollo 0.2%, zainetto minus 4 anni con
  `MinusBag`.
- `almgren_chriss_cost`, `compute_tax_penalty`, decision gating alimentato da
  EB_LB e riepilogo CLI aggiornato.
- Test unitari su matching FIFO/LIFO/min_tax, consumo/aggiunta minus, e errori
  di inventario.

## PR-22 — Mapping v2
- `rolling_beta_ridge`, bootstrap CI80, cap `c_beta`, TE-budget per fattore.
- CLI `fair3 map` con flag `--hrp-intra`, `--adv-cap`, `--te-factor-max`, `--tau-beta`.
- Test su CI ampi (riduzione pesi) e TE-budget.

## PR-23 — Goal Engine v2 ✅
- Monte Carlo regime-aware (≥10k percorsi) con contributi/riscatti, fan-chart e glidepath adattivo.
- CLI `fair3 goals --simulate`, CSV/PDf in `reports/goals_<investor>_*`, test sintetici su schedule e glidepath.

## PR-24 — Reporting v2 ✅
- `plot_fanchart`, `acceptance_gates`, `attribution_ic`, metric fan chart PNG, PDF mensili con gate e compliance log.
- Smoke test generazione PDF, controllo gate e CLI aggiornato.

## PR-25 — Mini GUI opzionale
- `launch_gui` (PySide6 opzionale) per orchestrare ingest/pipeline/log/report con tab Ingest/Pipeline/Reports.
- Fallback informativo quando PySide6 manca; CLI `fair3 gui` con flag percorso/dry-run.
- Test smoke (import/assenza dipendenza) e guida operativa in `docs/GUI.md`.

## PR-26…PR-48 — Ingest multi-fonte
- Implementare fetcher dedicati (ECB, FRED, French, AQR, Alpha Architect, BIS, OECD, World Bank, CBOE, Nareit, LBMA, Stooq,
  Yahoo, Alpha Vantage, Tiingo, CoinGecko, Binance, Portfolio Visualizer/testfol.io/us-market-data/backtes.to/portfoliocharts/
  Curvo).
- Ogni fetcher: `SOURCE`, `LICENSE`, `BASE_URL`, caching, controlli HTML, conversione EUR 16:00 CET, log licenza/URL, Parquet +
  SQLite, test offline con fixture.
- Aggiornare `fair3/engine/ingest/registry.py`, CLI `fair3 ingest`, documentazione e CHANGELOG per ogni fonte.

## PR-49 — QA end-to-end
- Esecuzione completa pipeline su dataset ridotto, verifica artefatti, acceptance gates, ablation.
- Aggiornare README, docs e seeds/checksum snapshot.

## PR-50 — Cleanup finale
- Revisione docstring Google-style, README modulari, template issue/PR, screenshot GUI, CHANGELOG finale.

### Rischi e mitigazioni
- **Rate limit / licenze:** implementare retry/backoff, caching ETag, log licenza esplicito.
- **Determinismo:** usare `audit/seeds.yml`, fissare `OMP/MKL/NUMEXPR` threads, test property su PSD/EB_LB.
- **Convergenza SPD median:** fallback Higham + log warning con suggerimenti.
- **Dataset manuali:** directory `data/*_manual/` con README esplicativi e test che saltano se mancano file.
