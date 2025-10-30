# Componenti principali FAIR-III

Questa mappa elenca i file chiave per sottosistema così da fornire all'agente punti di ingresso rapidi.

## CLI (`fair3/cli`)
- `main.py`: entrypoint CLI, parsing globale e comandi (`ingest`, `etl`, `factors`, `estimate`, `optimize`, `map`, `regime`, `execute`, `report`, `goals`, `qa`, `gui`).
- `__init__.py`: esporta `main` e helper CLI.

## Ingest (`fair3/engine/ingest`)
- `registry.py`: factory `create_fetcher`, orchestratore `run_ingest`, dichiarazione licenze.
- Fetcher HTTP/API: `ecb.py`, `fred.py`, `oecd.py`, `bis.py`, `boe.py`, `worldbank.py`, `coingecko.py`, `tiingo.py`, `alphavantage.py`, `binance.py`, `us_market_data.py`, `yahoo.py`, `stooq.py`, `cboe.py`.
- Fetcher manuali: `nareit.py`, `portfoliocharts.py`, `portfolio_visualizer.py`, `testfolio.py`, `curvo.py`, `aqr.py`, `alpha.py`, `lbma.py`, `eodhd.py`, `french.py`.
- Common utils: `BaseCSVFetcher`, `IngestArtifact` (schema output).

## ETL (`fair3/engine/etl`)
- `make_tr_panel.py`: orchestratore panel prezzi/rendimenti (classi `TRPanelBuilder`, `TRPanelArtifacts`).
- `cleaning.py`: Hampel, winsorization, normalizzazione prezzi.
- `calendar.py`: `TradingCalendar`, costruzione e riallineamento con timezone awareness.
- `fx.py`: gestione FX e conversioni a base comune.
- `qa.py`: modelli QA, scrittura log.

## Factors (`fair3/engine/factors`)
- `core.py`: definizione e calcolo fattori macro/mercato.
- `pipeline.py`: orchestrazione end-to-end con labeling e output.
- `validation.py`: metriche DSR/FDR, white reality check.
- `orthogonality.py`: merging ed enforcement di ortogonalità.

## Estimates (`fair3/engine/estimates`)
- `mean.py`, `covariance.py`: motori μ/Σ (Ledoit–Wolf, SPD median, shrinkage).
- `black_litterman.py`: fusione viste/equilibrio con fallback IR.
- `pipeline.py`: regia di cross-validation, gating diagnostico.

## Allocators (`fair3/engine/allocators`)
- `gen_a.py`: max-Sharpe vincolato.
- `gen_b_hrp.py`: HRP fattoriale.
- `gen_c_dro.py`: portafoglio DRO Wasserstein.
- `gen_d_cvar_erc.py`: combinazione CVaR + ERC.
- `meta.py`: meta-allocatore che pondera generatori con penalità.
- `constraints.py` / `objectives.py`: definizione di vincoli e funzioni obiettivo.
- `pipeline.py`: orchestrazione, salvataggio artefatti.

## Mapping (`fair3/engine/mapping`)
- `beta.py`: regressione ridge rolling, calcolo CI beta.
- `hrp_intra.py`: HRP intra-fattore.
- `liquidity.py`: guardrail su ADV e dimensioni trade.
- `te_budget.py`: enforcement budget tracking error.
- `pipeline.py`: step end-to-end per generare pesi strumentali.

## Regime (`fair3/engine/regime`)
- `committee.py`: comitato segnali (HMM, volatilità, macro slowdown).
- `hysteresis.py`: applicazione isteresi/cooldown.
- `pipeline.py`: output probabilità crisi, tilt λ e audit trail.

## Robustness (`fair3/engine/robustness`)
- `bootstrap.py`: bootstrap a blocchi deterministico.
- `scenarios.py`: scenari storici (1973, 2008, 2020, stagflazione).
- `ablation.py`: laboratori di governance.
- `lab.py`: orchestratore principale, link con artefatti QA.

## Reporting (`fair3/engine/reporting`)
- `analytics.py`: calcoli metriche (performance, TE, attribution).
- `monthly.py`: generazione pacchetto mensile (CSV, PDF).
- `plots.py`: grafici a ventaglio, breakdown costi/turnover.
- `audit.py`: sintesi di conformità e gate di accettazione.

## Goals (`fair3/engine/goals`)
- `mc.py`: simulatore Monte Carlo regime-aware con glidepath e contributi.

## Execution (`fair3/engine/execution`)
- `sizing.py`: dimensionamento ordini, lotti minimi.
- `tax.py`: euristiche fiscali italiane.
- `costs.py`: modelli Almgren–Chriss e slippage.
- `pipeline.py`: regia esecuzione deterministica, log audit.

## Universe & Brokers
- `fair3/engine/universe/`: unione universi broker, arricchimento ISIN/OpenFIGI.
- `fair3/engine/brokers/`: adattatori broker con mapping colonne.

## QA & Utils
- `fair3/engine/qa/`: pipeline demo deterministica, orchestrata da `fair3 qa`.
- `fair3/engine/utils/`: I/O, storage schema, logging, configurazione seme.
- `audit/function_inventory.py`: indice funzioni/artefatti per audit trail.

## Test suite (`tests/`)
- `tests/unit/`: test specifici per moduli (mock dati, QA deterministici).
- `tests/property/`: Hypothesis per invarianti statistiche.
- `tests/conftest.py`: marker `network` + opzione `--network` per isolare test con chiamate live.

Aggiornare questa tabella quando vengono aggiunti moduli pubblici o quando i pacchetti aggiornano i rispettivi `__all__`.
