# PR-15 Plan

## Scope
- Bump the FAIR-III package to **v0.2.0** and expose the version in `fair3.__init__`.
- Lay down repository scaffolding for the v0.2 roadmap: tracked `data/raw/` and `data/clean/` folders, audit placeholders,
  README/CHANGELOG updates, and roadmap alignment.
- Align tooling with the Google Python Style Guide: configure `black` and `ruff` (docstring checks), streamline pre-commit hooks,
  and ensure pytest runs automatically.

## Design Notes
- Centralise lint/format configuration inside `pyproject.toml` to avoid drift and enforce consistent rules (100-column limit,
  Google docstring convention, Python 3.11 target).
- Preserve deterministic seeds via `audit/seeds.yml` and introduce `audit/checksums.json` as the single source of truth for data
  artefact hashes (initially empty, to be filled in later PRs).
- Document the v0.2 command surface and compliance guardrails directly in the README so future contributors inherit the UCITS/EU/IT
  framing before touching code.

## Testing & Tooling
- Pre-commit should execute `ruff`, `black`, and `pytest` to catch linting/style/test regressions locally on every commit.
- CI and developers run: `ruff check .`, `black --check .`, `pytest -q`.
- No behavioural code changes are introduced in this scaffolding PR, but smoke commands (`fair3 --help`) should remain unaffected.


# PR-18 Plan (Regime Engine v2)

## Scope
- Replace the legacy committee with a deterministic HMM/HSMM implementation powered by `hmmlearn`.
- Extend hysteresis to support activation/deactivation streaks and expose new knobs in `configs/thresholds.yml`.
- Provide a full CLI command (`fair3 regime`) that loads the clean panel, persists artefacts under `artifacts/regime/` and emits structured metrics.

## Design Notes
- Introduce `regime_probability(panel, cfg, seed)` returning component diagnostics plus the combined crisis probability; keep `crisis_probability` as a compatibility wrapper.
- Build a regime pipeline orchestrator (`fair3/engine/regime/pipeline.py`) that loads Parquet panels or synthesises deterministic data when inputs are missing.
- CLI gains `--clean-root`, `--thresholds`, `--seed`, `--output-dir`, `--dry-run`, `--trace`; metrics are emitted via `record_metrics`.
- `apply_hysteresis` now enforces streak parameters in addition to dwell/cool-down to avoid flip-flops.

## Testing & Tooling
- Unit tests cover the new committee outputs, macro sensitivity, hysteresis streaks, pipeline artefact generation, and CLI wiring.
- Property tests ensure cooldown enforcement with the new streak parameters.
- Documentation (README, docs/VALIDATE.md, docs/roadmap.md, `fair3/engine/regime/README.md`) outlines the new workflow and knobs.


# PR-21 Plan (Execution & Tax IT v2)

## Scope
- Upgrade lot sizing to deterministic integer lots (`size_orders`) while retaining
  `target_to_lots` for backwards compatibility.
- Introduce aggregated Almgren–Chriss costs via `almgren_chriss_cost` and expose
  FIFO/LIFO/min_tax tax matching with four-year loss carry (`MinusBag`).
- Extend the CLI with `--tax-method` and document the richer execution pipeline.

## Design Notes
- Ensure `size_orders` validates shapes, handles zero/negative prices or lot sizes
  gracefully, and mirrors the Δw → lots formula used downstream.
- Implement `compute_tax_penalty` around DataFrame inputs so the future controller
  can plug instrument inventories directly; encapsulate minus management in
  `MinusBag` for reuse.
- Keep `tax_penalty_it` as a lightweight wrapper for quick heuristics while new
  dataclasses (`TaxRules`, `TaxComputation`) surface rich audit information.

## Testing & Tooling
- Extend `tests/unit/test_execution_primitives.py` to cover `size_orders` and the
  scalar Almgren–Chriss helper and guard the alias behaviour.
- Add dedicated tests for `compute_tax_penalty` covering FIFO/LIFO/min_tax, minus
  bag consumption, new-loss capture, and insufficient inventory errors.
- Refresh documentation (README, docs/FAIR-III.md, docs/roadmap.md,
  `fair3/engine/execution/README.md`) and update the plan/CHANGELOG to mark
  PR-21 as complete.


# PR-22 Plan (Mapping v2)

## Scope
- Extend beta estimation with sign priors, CI80-driven weight capping, and
  per-factor tracking-error governance to stabilise instrument allocations.
- Surface CLI overrides for per-factor TE caps and beta CI thresholds.
- Persist richer summary diagnostics (beta CI widths, factor deviation maxima)
  for downstream audit steps.

## Design Notes
- Rework `rolling_beta_ridge` to record enforcement metadata and support
  optional priors sourced from `factor_index.long_sign`.
- Add `cap_weights_by_beta_ci` and factor-level `enforce_te_budget` helpers so
  the pipeline can sequentially clip uncertain instruments and re-solve factor
  exposures before portfolio-level TE shrinkage.
- Update `run_mapping_pipeline` to wire the new governance steps, honour CLI
  overrides, and write normalised allocations after ADV clipping.

## Testing & Tooling
- Extend `tests/unit/test_mapping_beta.py` for sign enforcement and the new
  c-beta scaler, plus `tests/unit/test_mapping_te_budget.py` for factor-level
  TE clamps.
- Ensure CLI `fair3 map` accepts `--te-factor-max/--tau-beta` and re-run lint
  + unit suites to guard the deterministic behaviour.
- Refresh README, docs/FAIR-III.md, docs/roadmap.md, and the changelog to mark
  PR-22 as delivered.


# PR-24 Plan (Reporting v2)

## Scope
- Extend the reporting module with fan charts for wealth and key risk metrics,
  acceptance gate evaluation, attribution IC diagnostics, and PDF dashboards.
- Wire the new artefacts into the monthly report CLI and data classes while
  maintaining backwards compatibility for existing callers.

## Design Notes
- Reuse the bootstrap draws generated for the wealth fan chart to compute
  Sharpe, MaxDD, CVaR, EDaR, and CAGR trajectories; persist quantile bands as
  PNG charts.
- Introduce `acceptance_gates` and `attribution_ic` helpers so reporting and the
  robustness lab share governance logic; emit the acceptance summary as JSON and
  expose IC diagnostics for downstream QA.
- Generate a compact PDF (`reportlab`) combining metrics, compliance flags,
  acceptance gates, and chart artefacts; enrich `MonthlyReportArtifacts` with
  the new paths.

## Testing & Tooling
- Extend unit tests to cover the new artefacts (metric fan charts, acceptance
  JSON, PDF generation) and verify deterministic bootstrap paths.
- Add dedicated coverage for `acceptance_gates`, `attribution_ic`, and
  `plot_fanchart` error paths.
- Update README, module docs, and CHANGELOG to describe the expanded reporting
  workflow and CLI output.


# PR-27 Plan (FRED ingest extension)

## Scope
- Expand the FRED fetcher defaults to cover Treasury constant maturities (1Y-30Y),
  3M Treasury Bills, CPI headline, 5Y/10Y breakeven inflation, and 5Y/10Y TIPS real yields.
- Ensure the fetcher supports both JSON and ZIP CSV payloads for all defaults with
  deterministic parsing, NaN handling for ``."`` placeholders, and start-date filtering.
- Refresh ingest documentation, data source catalogues, and changelog notes to reflect
  the richer default coverage for macro features.

## Design Notes
- Keep credential validation unchanged but surface the extended ``DEFAULT_SYMBOLS`` tuple
  for reuse by CLI callers and documentation. The tuple order mirrors curve tenors to
  preserve audit readability.
- Reuse the existing ZIP parsing logic and reinforce unit coverage to guard the default
  symbol set, default-run behaviour, and metadata bookkeeping.
- Update ingest docs to list the default series explicitly so operators know which
  macro drivers they obtain out-of-the-box when running ``fair3 ingest --source fred``.

## Testing & Tooling
- Add unit tests that assert the expected default tuple and simulate a default fetch run
  via monkeypatched downloads, verifying symbol coverage, metadata length, and dtype
  normalisation.
- Re-run ``ruff``, ``black``, and ``pytest`` and ensure offline fixtures still exercise the
  ZIP parsing path for CSV exports.


# PR-28 Plan (Kenneth French ingest)

## Scope
- Introduce a `FrenchFetcher` subclass that downloads ZIP/TXT payloads from the Kenneth
  R. French Data Library, covering market factors, five-factor 2x3, momentum, and 49
  industry portfolios.
- Normalise the datasets into the FAIR ingest schema by reshaping factors to long format,
  scaling percent returns to decimals, and generating deterministic `<dataset>_<factor>`
  identifiers.
- Update ingest/README, data catalogues, and roadmap entries so operators understand
  the new default universe and licensing constraints (educational use only).

## Design Notes
- Extend `BaseCSVFetcher` via a dedicated fetcher that enforces ZIP downloads,
  detects HTML/rate-limit responses, and infers headers when the dataset definition
  omits explicit factor names (e.g., industry portfolios).
- Provide declarative dataset metadata (`FrenchDataset`) to keep filename, column
  selection, scaling, and sentinel handling co-located and testable.
- Ensure symbol normalisation is deterministic and Google-style naming compliant,
  while storing audit metadata (license, URL, requests) identical to other fetchers.

## Testing & Tooling
- Add unit coverage for parsing market factors and industry payloads, header inference,
  start-date filtering, and metadata bookkeeping.
- Extend CLI/registry tests so `french` appears in `available_sources()` and
  document the defaults in ingest docs and README.
- Run ``ruff``, ``black``, ``pytest`` offline to guarantee deterministic behaviour.

# PR-29 Plan (AQR datasets ingest)

## Scope
- Implement an `AQRFetcher` that ingests Quality-Minus-Junk, Betting-Against-Beta,
  and Value factor CSVs placed manually under `data/aqr_manual/`, while keeping the
  door open for HTTP downloads via declarative metadata.
- Normalise the datasets into the FAIR ingest schema (date/value/symbol) with
  deterministic monthly end dating and percent-to-decimal scaling.
- Refresh ingest documentation, README data tables, and the roadmap to document the
  manual workflow and licensing constraints (“educational use only”).

## Design Notes
- Describe dataset metadata with a frozen dataclass capturing filenames, date/value
  columns, scaling, and optional URLs so new series can be plugged in without
  altering the fetcher core.
- Override `_download` to interpret a custom `manual://` scheme, surfacing a helpful
  `FileNotFoundError` when users forget to place the CSV, while delegating standard
  HTTP downloads to `BaseCSVFetcher` for future automation.
    - Guard against accidental HTML payloads (e.g., login or rate-limit pages) by
  checking payload prefixes before parsing and raising a descriptive `ValueError`.

## Testing & Tooling
- Add unit tests that create temporary manual directories, write sample CSVs, and
  validate scaling, date normalisation, metadata, and CSV outputs.
- Cover error paths for missing manual files and HTML payload detection.
- Extend registry/import tests so `aqr` appears in `available_sources()` and run
  `ruff`, `black`, and `pytest` to keep the suite green.


# PR-31 Plan (BIS REER/NEER ingest)

## Scope
- Implement a `BISFetcher` that requests REER/NEER series from the SDMX endpoint
  (`https://stats.bis.org/api/v1/data`) using declarative `<dataset>:<area>:<freq>`
  symbols (defaulting to `REER:USA:M` and `NEER:USA:M`).
- Normalise the CSV payloads into the FAIR ingest schema (date/value/symbol),
  converting `TIME_PERIOD` into timestamps and coercing numeric values while
  filtering out malformed rows.
- Update ingest documentation, data source catalogues, and the roadmap so
  operators understand the BIS workflow, licensing, and manual requirements.

## Design Notes
- Reuse `BaseCSVFetcher` networking with stricter validation helpers that parse
  symbol components, enforce ISO-3 area codes, and map frequencies to
  `startPeriod` formatting (monthly, quarterly, annual).
- Harden the parser by normalising headers (upper + underscore), rejecting HTML
  payloads indicative of rate limits, and keeping the implementation dependency
  free.
- Surface descriptive error messages when the payload lacks `TIME_PERIOD` or
  `OBS_VALUE`, or when the user passes symbols in the wrong format.

## Testing & Tooling
- Add unit tests that monkeypatch `_download` with CSV fixtures, verifying start
  filtering, metadata contents, value coercion, and HTML rejection.
- Extend registry tests to include the new `bis` source and keep CLI listings in
  sync.
- Run `ruff`, `black`, and `pytest` to confirm the new fetcher integrates without
  regressions.


# PR-32 Plan (OECD ingest)

## Scope
- Implement an `OECDFetcher` that requests CLI/PMI series from the SDMX endpoint
  (`https://stats.oecd.org/sdmx-json/data`) using `<dataset>/<keys>` symbols with
  default coverage for the Composite Leading Indicator (Italy and euro area).
- Ensure the fetcher applies standard parameters (`contentType=csv`,
  `dimensionAtObservation=TimeDimension`, `timeOrder=Ascending`) and supports
  `startTime` filtering derived from CLI arguments.
- Update ingest documentation, data catalogues, roadmap, and changelog while
  exposing the new source via `available_sources()` and the CLI.

## Design Notes
- Split symbol paths and optional query strings, merging user-provided parameters
  with the defaults via `urllib.parse` helpers while guarding against empty
  paths.
- Normalise CSV headers (upper + underscore), accept both `TIME_PERIOD` and
  fallback labels (`TIME`, `DATE`), and treat `OBS_VALUE`/`VALUE` as candidate
  value columns.
- Reject HTML payloads with explicit `ValueError` messages so callers can retry
  or fall back gracefully.

## Testing & Tooling
- Unit tests covering default symbols, URL composition (`startTime`, parameter
  overrides), CSV parsing, and error handling for HTML or missing columns.
- Extend registry tests to ensure `oecd` appears in `available_sources()`.
- Run `ruff`, `black`, and `pytest` to keep the ingest suite deterministic.


# PR-33 Plan (World Bank ingest)

## Scope
- Introduce a `WorldBankFetcher` that consumes the v2 JSON API, handles
  pagination metadata (`page`, `pages`, `per_page`), e normalizza le serie nel
  formato FAIR (`date`, `value`, `symbol`).
- Supportare simboli multi-paese (`<indicatore>:<ISO3;ISO3>`) e impostare come
  default popolazione totale e PIL reale per l'Italia.
- Registrare sempre la licenza "World Bank Open Data Terms" e tracciare le
  richieste effettuate per ogni pagina.

## Design Notes
- Riutilizzare la serializzazione CSV del `BaseCSVFetcher` ma sovrascrivere il
  loop `fetch` per aggregare tutte le pagine JSON prima di applicare il filtro
  `--from`.
- Validare i payload: rifiutare HTML, convertire le stringhe numeriche dei
  metadati in interi, rimuovere valori nulli, comporre simboli come
  `<indicatore>:<ISO3>` sfruttando `countryiso3code`.
- Evitare dipendenze extra (niente `pandasdmx`): usare solo `json` della
  standard library e `pandas`.

## Testing & Tooling
- Scrivere test unitari che verificano aggregazione multi-pagina, filtro `start`,
  gestione di simboli malformati e payload HTML.
- Estendere i test di registry/CLI per includere `worldbank` e verificare i
  simboli di default.
- Aggiornare README, docs/DATA.md, ingest README, roadmap e changelog con la
  nuova fonte World Bank.

## PR-34 Plan (CBOE VIX/SKEW ingest)

## Scope
- Implementare `CBOEFetcher` con mapping dichiarativo dei file pubblici (`VIX_History.csv`, `SKEW_History.csv`) e guardia HTML per risposte di errore.
- Normalizzare i CSV in formato FAIR (`date`, `value`, `symbol`) mantenendo il simbolo upper-case, applicare il filtro `--from` post-download e loggare licenza/URL.
- Aggiornare registry/CLI/README/docs (tabella fonti) e aggiungere test unitari su parsing, filtro start e gestione di simboli non supportati.

## Design Notes
- Riutilizzare `_simple_frame` oppure parsing custom con dizionari di rename per gestire header differenti ("VIX Close", `SKEW`).
- Rifiutare payload HTML o simboli sconosciuti con `ValueError` descrittivi e mantenere licenza/URL nei metadati dell'`IngestArtifact`.
- Mantenere il simbolo maiuscolo nella colonna `symbol` per evitare mismatch con altre pipeline.

## Testing & Tooling
- Scrivere test unitari che monkeypatchano `_download` per VIX/SKEW, verificano filtro `--from`, licenza nei metadati e gestione errori HTML.
- Estendere i test di registry/CLI affinché `cboe` appaia in `available_sources()`.
- Aggiornare README, docs/DATA.md, ingest README, roadmap e changelog per documentare la nuova fonte e rieseguire `ruff`, `black`, `pytest`.

## PR-35 Plan (Nareit manual ingest)

## Scope
- Implementare `NareitFetcher` che legge gli Excel manuali (`NAREIT_AllSeries.xlsx`) con mapping dichiarativo di foglio, colonne e scaling.
- Validare la presenza del file manuale, normalizzare date a fine mese e valori Total Return per All Equity e Mortgage REIT.
- Aggiornare registry, CLI docs, README, roadmap, plan e changelog; predisporre directory `data/nareit_manual/` nella documentazione.

## Design Notes
- Riutilizzare `SeriesSpec` con campi `sheet_name`, `date_column`, `value_column`, `frequency` per gestire future estensioni (quarterly, altre serie).
- Usare `pandas.read_excel` con `BytesIO` per supportare payload manuali o HTTP; verificare colonne e scalare valori se espresso in percentuale.
- Documentare la licenza “for informational purposes only” nei log/metadati e mantenere start filter post parsing.

## Testing & Tooling
- Creare test unitari che monkeypatchano `_download` e `pd.read_excel` per restituire DataFrame sintetici, verificando filtro `--from` e licenza nei metadati.
- Testare l'errore `FileNotFoundError` quando l'Excel non è presente e `ValueError` per colonne mancanti.
- Estendere i test di registry/CLI affinché `nareit` compaia in `available_sources()` ed eseguire `ruff`, `black`, `pytest` prima del commit.

## PR-36 Plan (LBMA metals ingest)

## Scope
- Implementare `LBMAFetcher` che estrae le tabelle HTML dei fixing pomeridiani per oro e argento.
- Convertire i prezzi USD in EUR tramite i cambi BCE (serie `D.USD.EUR.SP00.A`) e impostare `pit_flag` quando l'orario corrisponde alle 16:00 CET.
- Aggiornare registry, CLI docs, README, roadmap, plan e changelog; documentare la directory di output e la licenza LBMA.

## Design Notes
- Utilizzare `pandas.read_html` e selezionare la prima tabella con colonna `Date`, normalizzando eventuali header duplicati.
- Localizzare i timestamp a `Europe/London`, convertirli a `Europe/Rome` per il calcolo di `pit_flag`, quindi salvare l'istante in UTC senza timezone.
- Caricare i cambi USD/EUR da cache (`fx_rates`) o, se assenti, invocare `ECBFetcher` e memorizzare i risultati in `_fx_cache` con forward-fill per festività/weekend.

## Testing & Tooling
- Creare fixture HTML sintetiche con colonne `Date` e `USD (PM)` e monkeypatchare `_load_fx_rates` per restituire cambi deterministici.
- Testare parsing positivo, rifiuto di payload HTML senza tabella, errore per simbolo sconosciuto e fallback FX mancante.
- Estendere i test di registry/CLI affinché `lbma` compaia in `available_sources()` ed eseguire `ruff`, `black`, `pytest` prima del commit.

## PR-37 Plan (Stooq ingest hardening)

## Scope
- Rafforzare `StooqFetcher` con normalizzazione `.us/.pl`, colonna `tz="Europe/Warsaw"` e cache in-process dei payload.
- Aggiornare registry, CLI docs, README, roadmap, plan e changelog per descrivere il nuovo comportamento.
- Garantire che il filtro `--from` continui a essere applicato post parsing e che i simboli siano esportati in upper-case.

## Design Notes
- Sovrascrivere `_download` per utilizzare un cache (dict) chiave→payload basato sul parametro `s` dell'URL.
- Normalizzare i simboli in lower-case per la query e upper-case per l'output, mantenendo compatibilità con suffissi `.us`/`.pl`.
- Estendere `parse` per accettare `bytes`, validare header CSV, convertire i valori in `float` e aggiungere `tz` senza alterare l'ordinamento temporale.

## Testing & Tooling
- Aggiornare i test offline (`tests/unit/test_stooq_fetcher_offline.py`) per verificare cache, filtro start e gestione HTML.
- Estendere i test di registry/CLI per assicurare la presenza della colonna `tz` e la normalizzazione del simbolo.
- Eseguire `ruff`, `black`, `pytest` prima del commit e registrare gli aggiornamenti documentali nelle sedi richieste.

## PR-38 Plan (Yahoo fallback ingest)

## Scope
- Implementare `YahooFetcher` come fallback basato su `yfinance`, rispettando una finestra massima di cinque anni e un ritardo di due secondi tra le richieste.
- Registrare la nuova sorgente nel registry e aggiornare README, docs/DATA.md, ingest README, roadmap, plan e changelog con note su licenza e dipendenza opzionale.
- Assicurare che il fetcher funzioni anche senza `yfinance` installato (errore esplicativo) e che l'utente possa ridurre il ritardo nei test.

## Design Notes
- Utilizzare uno schema pseudo `yfinance://<SYMBOL>?start=<ISO>` per propagare parametri e riutilizzare le infrastrutture esistenti di `BaseCSVFetcher`.
- Applicare `_clamp_start` per limitare l'intervallo, convertire le serie in CSV canonici (`date`, `value`) e inserire `time.sleep(delay_seconds)` solo dopo il download.
- Esporre `_import_yfinance` e `_now` come helper separati per facilitare i test; rilevare le colonne `Date`/`Close` o `Adj Close` restituite da `yfinance`.

## Testing & Tooling
- Aggiungere `tests/unit/test_yahoo_fetcher.py` per coprire URL, parsing, filtro start, enforcement finestra e mancanza di `yfinance`.
- Estendere `tests/unit/test_ingest_registry.py` per verificare la presenza della sorgente `yahoo`.
- Aggiornare la documentazione e rieseguire `ruff`, `black`, `pytest` assicurandosi che i test saltino quando `yfinance` manca.

## PR-39 Plan (Alpha Vantage FX ingest)

## Scope
- Implementare `AlphaVantageFXFetcher` per serie FX giornaliere (`function=FX_DAILY`) con coppie EUR (default: USD, GBP, CHF).
- Gestire la chiave API tramite parametro o variabile d'ambiente `ALPHAVANTAGE_API_KEY`, evitando che il valore compaia nei log/metadata.
- Applicare throttling deterministico (intervallo ≥12s) per rispettare il rate limit gratuito e trasformare gli errori JSON (`Note`, `Error Message`) in eccezioni leggibili.

## Design Notes
- Costruire URL sanitizzati senza `apikey`, aggiungendo il parametro solo in `_download` prima della chiamata HTTP.
- Supportare formati di simbolo `AAA`, `AAA/BBB` e `AAABBB`, assumendo EUR come controvaluta quando non specificata.
- Riutilizzare `_simple_frame` per normalizzare il CSV (`timestamp`, `close`) e filtrare `start` post-download; rilevare payload HTML/JSON per segnalare rate limit.

## Testing & Tooling
- Aggiungere `tests/unit/test_alphavantage_fetcher.py` con casi su parsing CSV, rate limit JSON, throttling, mascheramento URL e simboli invalidi.
- Estendere `tests/unit/test_ingest_registry.py` e la documentazione (README, docs/DATA.md, ingest README, roadmap, changelog) con la nuova sorgente.
- Rieseguire `ruff`, `black`, `pytest`; nei test impostare `throttle_seconds=0` per evitare attese artificiali.

## PR-40 Plan (Tiingo ingest)

## Scope
- Implementare `TiingoFetcher` per prezzi daily equities/ETF via endpoint `https://api.tiingo.com/tiingo/daily/<symbol>/prices`.
- Richiedere `TIINGO_API_KEY` (parametro o env var) e applicare throttling deterministico per rispettare il contratto API.
- Normalizzare il payload JSON (`adjClose`/`close`) nel formato FAIR (`date`, `value`, `symbol`) e gestire payload HTML o colonne mancanti.

## Design Notes
- Costruire URL sanificati includendo `startDate` quando il CLI fornisce `--from`; evitare di loggare la chiave API nei metadati.
- Implementare `_download` personalizzato con header `Authorization: Token <key>` e retry/backoff come nel `BaseCSVFetcher`.
- Riutilizzare `pandas` per convertire la lista JSON in DataFrame, selezionare `adjClose` (fallback `close`), convertire le date a UTC e rimuovere osservazioni nulle.

## Testing & Tooling
- Creare `tests/unit/test_tiingo_fetcher.py` coprendo URL, chiave mancante, parsing JSON, payload HTML e registrazione nel registry.
- Aggiornare `tests/unit/test_ingest_registry.py` per includere `tiingo` e documentazione (README, docs/DATA.md, ingest README, roadmap, changelog).
- Rieseguire `ruff`, `black`, `pytest` assicurandosi che i test saltino correttamente quando le dipendenze opzionali non sono presenti.

## PR-41 Plan (CoinGecko ingest)

## Scope
- Implementare `CoinGeckoFetcher` basato sull'endpoint `coins/<id>/market_chart/range` con throttle deterministico e sampling alle 16:00 CET.
- Normalizzare i dati in EUR, aggiungere `currency` e `pit_flag`, garantire default (`bitcoin`, `ethereum`) e gestione errori (HTML, payload `error`).

## Design Notes
- Costruire URL con `from`/`to` derivati da `start` (UTC) e `now_fn` iniettato per i test; default a cinque anni indietro quando `start` è assente.
- Applicare throttling tramite `time.monotonic`, calcolare il punto giornaliero più vicino a 15:00 UTC (16:00 CET) e impostare `pit_flag=1` se la differenza è ≤15 minuti.
- Restituire DataFrame con colonne `date`, `value`, `symbol`, `currency`, `pit_flag` ordinato cronologicamente.

## Testing & Tooling
- Creare `tests/unit/test_coingecko_fetcher.py` per verificare sampling, `pit_flag`, licenza, error handling e costruzione URL (inclusi default di 5 anni).
- Aggiornare `tests/unit/test_ingest_registry.py` e la documentazione (README, docs/DATA.md, ingest README, roadmap, changelog) con la nuova sorgente.
- Rieseguire `ruff`, `black`, `pytest` garantendo che il throttle sia disattivabile nei test (`delay_seconds=0`).

## PR-42 Plan (Binance Data Portal ingest)

## Scope
- Implementare `BinanceFetcher` per scaricare i file ZIP giornalieri `data/spot/daily/klines/<symbol>/<interval>/` con default `BTCUSDT`.
- Normalizzare le colonne open/high/low/close/volume, derivare la valuta quotata e valorizzare `pit_flag`/`tz` nei DataFrame restituiti.
- Supportare `--from` e `--symbols`, gestire intervalli mancanti (404) con log e metadati dedicati, mantenendo l'intervallo massimo a 365 giorni quando `start` è assente.

## Design Notes
- Riutilizzare `_download` personalizzato per restituire bytes ZIP e decomprimere in memoria selezionando il membro CSV deterministico.
- Iterare sui giorni con `tqdm` opzionale, annotando `status` (`ok`/`missing`) per ciascuna richiesta nei metadati e filtrando le date in UTC naive dopo la concatenazione.
- Derivare la valuta quotata tramite suffissi noti (USDT, BUSD, EUR, ecc.) con fallback `UNKNOWN`; assicurare che i log riportino licenza e intervallo richiesto.

## Testing & Tooling
- Aggiungere `tests/unit/test_binance_fetcher.py` per coprire parsing ZIP, concatenazione multi-day, gestione dei 404 e rifiuto dei payload HTML.
- Estendere `tests/unit/test_ingest_registry.py` e la documentazione (README, docs/DATA.md, ingest README, roadmap, changelog) con la sorgente `binance`.
- Rieseguire `ruff`, `black`, `pytest`; nei test utilizzare payload sintetici in-memory per evitare chiamate di rete.

## PR-43 Plan (Portfolio Visualizer references ingest)

## Scope
- Implementare `PortfolioVisualizerFetcher` per CSV mensili scaricati da Portfolio Visualizer (US Total Stock Market, International Developed Market, US Total Bond Market, Gold Total Return).
- Normalizzare i file nel formato FAIR (`date`, `value`, `symbol`) scalando automaticamente la colonna `Return` e allineando le date a fine mese.
- Documentare la directory manuale `data/portfolio_visualizer_manual/`, registrare la sorgente `portviz` nel registry/CLI e aggiornare README, docs/DATA.md, roadmap e changelog.

## Design Notes
- Definire una dataclass `PortfolioVisualizerDataset` per mantenere dichiarativa la configurazione dei dataset (filename, colonne, scala, frequenza, eventuale rename).
- Gestire lo schema `manual://` in `_download` e produrre messaggi d'errore chiari per file mancanti o payload HTML.
- Applicare `MonthEnd(0)` ai dataset mensili e prevedere il campo `rename` per supportare futuri alias dei simboli Portfolio Visualizer.

## Testing & Tooling
- Aggiungere `tests/unit/test_portfolio_visualizer_fetcher.py` con casi su parsing positivo, filtro `start`, assenza file, colonne mancanti e payload HTML.
- Aggiornare `tests/unit/test_ingest_registry.py` per includere `portviz` e rieseguire `ruff`, `black`, `pytest` assicurando la determinismo della suite.
- Esplicitare nella documentazione ingest la licenza “Portfolio Visualizer — informational/educational use” e i passaggi per popolare `data/portfolio_visualizer_manual/`.
