# Changelog

## [0.2.0] - 2024-09-18
### Added
- Repository scaffolding for FAIR-III v0.2 roadmap (data lake folders, audit checksum placeholder, refreshed README with
  Quickstart v0.2, CLI reference, UCITS/EU/IT compliance guidance).
- Tooling alignment with Google Python Style Guide: `black` 100-col limit, `ruff` Google docstring checks, pytest pre-commit
  hook, consolidated configuration in `pyproject.toml`.
- Configuration validator CLI (`fair3 validate`) leveraging pydantic schemas with verbose output and
  dedicated unit tests.
- Structured observability primitives: `fair3.engine.logging.setup_logger`, JSON audit mirroring, metrics
  JSONL writer, CLI-wide `--progress/--json-logs` flags, and refreshed docs/tests capturing the new
  workflow.
- Regime Engine v2: `regime_probability`, hysteresis streak controls, CLI `fair3 regime` with artefact
  persistence (`probabilities.csv`, `hysteresis.csv`, `committee_log.csv`), and validation updates for
  committee/macro weights.
- Covariance consensus upgrades: optional SPD geometric median (`sigma_spd_median`), CLI flag
  `--sigma-engine`, PSD/ordering property tests, and refreshed documentation for the estimation
  pipeline.
- Block-bootstrap expected benefit engine: `block_bootstrap`, EB distribution helpers, EB_LB
  monotonicity tests, and documentation updates for execution guardrails.
- Execution & Tax IT v2: `size_orders` lot sizing upgrade, Almgren–Chriss scalar
  helper, Italian tax engine (`compute_tax_penalty`, `MinusBag`) with CLI
  `--tax-method` wiring and refreshed documentation/tests.
- Mapping v2: rolling ridge betas with sign priors, CI80-driven weight caps,
  per-factor tracking-error governance, new CLI overrides (`--te-factor-max`,
  `--tau-beta`), and extended tests/documentation for mapping controls.
- Goal Engine v2: regime-aware Monte Carlo con contributi/riscatti programmati,
  glidepath adattivo, fan-chart mensili, CLI `fair3 goals --simulate`, output in
  `reports/`, e test aggiornati su schedule/glidepath.
- Reporting v2: metric fan charts, acceptance gate evaluation, attribution IC
  diagnostics, PDF summaries, CLI enhancements, and documentation/tests for the
  expanded reporting workflow.
- Mini GUI opzionale: `launch_gui`, comando `fair3 gui` con flag di percorso,
  fallback quando PySide6 manca, documentazione dedicata e test smoke con
  stub/assenza dipendenza.
- Ingest FRED esteso: default con curve Treasury 1-30Y, DTB3, CPI, breakeven
  5Y/10Y e TIPS 5Y/10Y, con test offline JSON/ZIP e documentazione aggiornata.
- Ingest Kenneth French: fetcher dedicato con fattori mensili, pacchetto 5x5,
  momentum e 49 industrie, parsing ZIP/TXT con normalizzazione long-form e
  documentazione/QA aggiornati.
- Ingest AQR: fetcher manuale/HTTP con mapping dichiarativo (QMJ, BAB, VALUE),
  scaling percentuale→decimale, gestione `manual://`, documentazione e test
  offline sui percorsi manuali.
- Ingest Alpha/q-Factors/Novy-Marx: fetcher misto CSV/HTML con percorsi manuali,
  scaling delle percentuali, integrazione CLI/documentazione e test dedicati.
- Ingest BIS REER/NEER: fetcher SDMX con simboli `<dataset>:<area>:<freq>`,
  normalizzazione `TIME_PERIOD`/`OBS_VALUE`, gestione `startPeriod` e aggiornamento
  della documentazione ingest/data.
- Ingest OECD CLI/PMI: fetcher SDMX (`OECDFetcher`) con parametri `contentType=csv`,
  `dimensionAtObservation=TimeDimension`, default CLI Italia/area euro, parser CSV
  resiliente e documentazione/registry aggiornati.
- Ingest World Bank: fetcher JSON con paginazione automatica, simboli normalizzati
  `<indicatore>:<ISO3>`, default popolazione/PIL Italia, metadati pagina nei log e
  documentazione aggiornata (README, ingest README, data catalog, roadmap, plan).
- Ingest CBOE: fetcher CSV (`CBOEFetcher`) per VIX/SKEW con guardia HTML, filtro
  `--from` post-download, simboli upper-case e documentazione/registry/plan
  aggiornati.
- Ingest Nareit: fetcher manuale (`NareitFetcher`) per gli indici FTSE Nareit
  Total Return (All Equity, Mortgage), parsing Excel locale con controllo
  colonne, date end-of-month e aggiornamento documentazione/registry/plan.
- Ingest LBMA: fetcher HTML (`LBMAFetcher`) per i fixing oro/argento delle
  15:00 London, conversione USD→EUR via `ECBFetcher`, popolamento `pit_flag`
  alle 16:00 CET, documentazione/registry/plan aggiornati e test offline per
  parsing/FX fallback.
- Ingest Stooq: fetcher con normalizzazione `.us/.pl`, colonna `tz="Europe/Warsaw"`,
  cache in-process dei payload, documentazione aggiornata e suite offline per
  caching/filtro start/simboli upper-case.
- Ingest Yahoo fallback: `YahooFetcher` basato su `yfinance` con finestra
  massima di cinque anni, ritardo di due secondi configurabile, gestione della
  dipendenza opzionale e documentazione/test aggiornati.
- Ingest Alpha Vantage FX: `AlphaVantageFXFetcher` con throttling deterministico,
  sanitizzazione dell'URL (nessuna esposizione `apikey`), parsing CSV `FX_DAILY`
  e documentazione/test aggiornati su licenza e chiave API.
- Ingest Tiingo: `TiingoFetcher` con autenticazione tramite `TIINGO_API_KEY`,
  throttling deterministico, parsing JSON (`adjClose`/`close`), guardie HTML e
  aggiornamenti documentali/tests/registry.
- Ingest CoinGecko: `CoinGeckoFetcher` con endpoint `market_chart/range`,
  throttling minimo (1s), campionamento alle 16:00 CET con `pit_flag`, default
  `bitcoin`/`ethereum` e documentazione/tests/registry aggiornati.
- Ingest Binance Data Portal: `BinanceFetcher` per ZIP giornalieri `klines`,
  concatenazione multi-day con inferenza valuta quotata, gestione dei 404 con
  metadati `status` e aggiornamenti a documentazione/registry/test.
- Ingest Portfolio Visualizer references: `PortfolioVisualizerFetcher` per CSV mensili scaricati manualmente (US Total Stock Market, International Developed Market, US Total Bond Market, Gold Total Return) con scaling percentuale→decimale, directory `data/portfolio_visualizer_manual/` documentata e test su parsing/start/html/colonne.

### Changed
- Bumped package version to `0.2.0` in `pyproject.toml` and exposed the version in `fair3.__init__` for runtime introspection.

### Notes
- Questa release costituisce la base per le PR PR-16 → PR-50 (regime v2, Σ SPD-median, bootstrap v2, execution & tax v2,
  mapping v2, goals v2, reporting v2, ingest multi-fonte, mini GUI).
- Tutti i componenti restano marcati come preview: l'utilizzo è limitato a scopi educativi e di ricerca.
