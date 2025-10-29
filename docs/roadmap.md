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

## PR-27 — FRED ingest extension ✅
- Estendere `FREDFetcher` con default Treasury 1-30Y, DTB3, CPI, breakeven 5Y/10Y e TIPS 5Y/10Y.
- Aggiornare documentazione ingest/dati e CHANGELOG; aggiungere test offline JSON/ZIP e verifica default tuple.

## PR-28 — Kenneth French ingest ✅
- Nuovo `FrenchFetcher` con fattori di mercato (Mkt-RF, SMB, HML, RF), pacchetto 5x5, momentum e portafogli 49 industrie.
- Parsing ZIP/TXT con inferenza header, normalizzazione a formato lungo (`<dataset>_<fattore>`), scaling percentuale→decimale e gestione sentinel.
- Documentazione ingest/README/dataset aggiornata e test offline su fattori e industrie.

## PR-29 — AQR datasets ingest ✅
- `AQRFetcher` con mapping dichiarativo (`qmj_us`, `bab_us`, `value_global`) e fallback `manual://` per i file CSV scaricati dall'utente.
- Parsing deterministico con scaling percentuale→decimale, validazione HTML e controllo colonne; logging licenza "educational use".
- Aggiornamento documentazione (README, docs/DATA.md, ingest README) e test unitari su percorsi manuali mancanti/presenti.

## PR-30 — Alpha/q-Factors/Novy-Marx ingest ✅
- `AlphaFetcher` con metadata dichiarativi per CSV pubblici e drop manuali HTML (`data/alpha_manual/`).
- Parser che gestisce CSV, percentuali e tabelle HTML senza dipendenze extra, con normalizzazione mensile e scaling coerente.
- Documentazione aggiornata (README, docs/DATA.md, ingest README) e test unitari per percorsi HTTP/manuali e registrazione licenze.

## PR-31 — BIS REER/NEER ingest ✅
- `BISFetcher` per REER/NEER via SDMX (`https://stats.bis.org/api/v1/data/<dataset>/<freq>.<area>`), con gestione `startPeriod`.
- Normalizzazione CSV (`TIME_PERIOD`/`OBS_VALUE`), filtro HTML e simboli `<dataset>:<area>:<freq>` con validazioni frequenza/ISO-3.
- README, docs/DATA.md e ingest README aggiornati; test unitari su parsing, start rounding e registrazione della nuova sorgente.

## PR-32 — OECD ingest ✅
- `OECDFetcher` per CLI/PMI via SDMX (`https://stats.oecd.org/sdmx-json/data/<dataset>/<keys>`), con parametri
  `contentType=csv`, `dimensionAtObservation=TimeDimension`, `timeOrder=Ascending` e supporto `startTime`.
- Parser CSV resiliente (`TIME_PERIOD`/`OBS_VALUE`), guardia HTML, normalizzazione header e default su Composite Leading Indicator
  Italia + area euro.
- Documentazione (README, docs/DATA.md, ingest README, roadmap) e test unitari su URL, parsing, errori HTML/colonne mancanti.

## PR-33 — World Bank ingest ✅
- `WorldBankFetcher` con gestione paginazione JSON (`per_page=20000`) e normalizzazione dei simboli `<indicatore>:<ISO3>`.
- Default popolazione e PIL reale per Italia, filtro `--from` gestito post-download e log licenza "World Bank Open Data Terms".
- Documentazione aggiornata (README, docs/DATA.md, ingest README, plan) e test unitari per pagine multiple, filtro start e payload HTML.

## PR-34 — CBOE ingest ✅
- `CBOEFetcher` per serie VIX/SKEW via CSV pubblico (`cdn.cboe.com/api/global/us_indices/daily_prices`) con guardia HTML e simboli upper-case.
- Filtro `--from` applicato post-download, licenza `Cboe Exchange, Inc. data subject to terms` nei metadati, default `VIX`/`SKEW`.
- README, docs/DATA.md, ingest README, roadmap, plan e changelog aggiornati con test unitari su parsing, errori HTML e registry.

## PR-35 — Nareit ingest ✅
- `NareitFetcher` che legge Excel manuali (`data/nareit_manual/NAREIT_AllSeries.xlsx`), valida colonne e allinea le date a fine mese.
- Normalizzazione degli indici Total Return (All Equity e Mortgage REIT) con licenza “for informational purposes only” nei metadati.
- Aggiornamento README, docs/DATA.md, ingest README, roadmap, plan e changelog con test unitari su parsing, errori HTML e registry.

## PR-36 — LBMA metals ingest ✅
- `LBMAFetcher` per fixing oro/argento delle 15:00 London via tabelle HTML (`lbma.org.uk/prices-and-data/precious-metal-prices`).
- Conversione automatica USD→EUR tramite `ECBFetcher` (serie `D.USD.EUR.SP00.A`), popolamento `pit_flag` alle 16:00 CET e cache dei cambi.
- Documentazione aggiornata (README, docs/DATA.md, ingest README, plan, changelog) e test unitari su parsing, errori HTML e fallback FX.

## PR-37 — Stooq ingest hardening ✅
- Rafforzamento di `StooqFetcher` con normalizzazione `.us/.pl`, colonna `tz="Europe/Warsaw"` e cache in-process dei payload.
- Documentazione aggiornata (README, docs/DATA.md, ingest README, plan, changelog) per illustrare caching, timezone e filtri applicati post parsing.
- Estensione dei test offline/CLI su caching, filtro `--from` e simboli upper-case mantenendo `ruff`/`black`/`pytest` verdi.

## PR-38 — Yahoo fallback ingest ✅
- `YahooFetcher` basato su `yfinance` con finestra massima di cinque anni, ritardo configurabile (default 2s) e log licenza "personal/non-commercial use".
- Registrazione della nuova sorgente nel registry/CLI, aggiornamento documentazione (README, docs/DATA.md, ingest README, plan, changelog) e nota sulla dipendenza opzionale.
- Test unitari che coprono URL pseudo `yfinance://`, filtro `--from`, enforcement della finestra, assenza di `yfinance` e registrazione nel registry.

## PR-39 — Alpha Vantage FX ingest ✅
- `AlphaVantageFXFetcher` con parsing CSV `FX_DAILY`, throttling deterministico (5/min) e mascheramento dell'API key nei log.
- Lettura della chiave da `ALPHAVANTAGE_API_KEY` o parametro esplicito, gestione errori JSON (`Note`, `Error Message`) come `ValueError` e default su coppie EUR (USD, GBP, CHF).
- Documentazione aggiornata (README, docs/DATA.md, ingest README, plan, changelog) e test unitari su parsing, throttling, sanitizzazione metadati e registry.

## PR-40 — Tiingo ingest ✅
- `TiingoFetcher` con supporto a ticker azionari/ETF via endpoint `https://api.tiingo.com/tiingo/daily/<symbol>/prices` e throttling deterministico (1s).
- Gestione della chiave tramite `TIINGO_API_KEY` (header `Authorization: Token`), parsing JSON (`adjClose`/`close`), normalizzazione `date/value/symbol` e guardie HTML/colonne mancanti.
- Aggiornamento documentazione (README, docs/DATA.md, ingest README, roadmap, plan, changelog) e test unitari su URL, chiave mancante, parsing e registrazione della sorgente.

## PR-41 — CoinGecko ingest ✅
- `CoinGeckoFetcher` basato su `market_chart/range` con throttling minimo di 1s e supporto a simboli default (`bitcoin`, `ethereum`).
- Campionamento delle serie intraday alle 16:00 CET (15:00 UTC) con flag `pit_flag` quando la differenza è ≤15 minuti, conversione in EUR e normalizzazione `date/value/symbol/currency`.
- Documentazione aggiornata (README, docs/DATA.md, ingest README, roadmap, plan, changelog) e test unitari su URL, error handling (HTML, payload di errore) e registrazione nel registry.

## PR-42 — Binance Data Portal ingest ✅
- `BinanceFetcher` per gli archivi ZIP `data/spot/daily/klines/<symbol>/<interval>/`, concatenazione multi-day, inferenza valuta quotata e metadati `pit_flag`/`tz`.
- Gestione dei 404 giornalieri con log `binance_missing_day`, metadati `status` (`ok`/`missing`) e filtro `--from` applicato post-download in UTC naive.
- Documentazione aggiornata (README, docs/DATA.md, ingest README, roadmap, plan, changelog) e test unitari su parsing ZIP, gestione errori HTML e registrazione nel registry.

## PR-43 — Portfolio Visualizer references ingest ✅
- `PortfolioVisualizerFetcher` per CSV mensili scaricati manualmente (US Total Stock Market, International Developed Market, US Total Bond Market, Gold Total Return) con scala percentuale → decimale e allineamento MonthEnd.
- Directory `data/portfolio_visualizer_manual/` documentata nel README ingest, registrazione della nuova sorgente `portviz` nel registry/CLI e licenza “Portfolio Visualizer — informational/educational use”.
- Test unitari su parsing, filtro `start`, errori di colonne mancanti/HTML e aggiornamento di README, docs/DATA.md, roadmap e changelog.

## PR-49 — QA end-to-end ✅
- Comando `fair3 qa` che genera dataset sintetico, esegue la pipeline completa,
  produce report mensile, robustezza (bootstrap+ablation) e snapshot di audit.
- Documentazione aggiornata (`README`, `docs/QA.md`) e test di integrazione sul
  percorso QA con parametrizzazione rapida per CI.

## PR-50 — Cleanup finale ✅
- Revisione docstring Google-style nei moduli QA, README modulari per `fair3/`,
  CLI ed engine, screenshot GUI nella documentazione, template confermati e
  CHANGELOG aggiornato per chiudere la roadmap v0.2.

### Rischi e mitigazioni
- **Rate limit / licenze:** implementare retry/backoff, caching ETag, log licenza esplicito.
- **Determinismo:** usare `audit/seeds.yml`, fissare `OMP/MKL/NUMEXPR` threads, test property su PSD/EB_LB.
- **Convergenza SPD median:** fallback Higham + log warning con suggerimenti.
- **Dataset manuali:** directory `data/*_manual/` con README esplicativi e test che saltano se mancano file.
