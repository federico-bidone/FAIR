# Log delle modifiche

## [0.2.0] - 2024-09-18
### Aggiunto
- Struttura del repository per la roadmap di FAIR-III v0.2 (cartelle data Lake, segnaposto di checksum di audit, README aggiornato con
  Quickstart v0.2, riferimento CLI, linee guida sulla conformità UCITS/UE/IT).
- Allineamento degli strumenti con la guida allo stile di Google Python: `black` Limite di 100 colonne, `ruff`Controlli delle docstring di Google, pre-commit pytest
  hook, configurazione consolidata in `pyproject.toml`.
- Configuration validator CLI (`fair3 validate`) che sfrutta schemi pydantic con output dettagliato e unit test dedicati
  .
- Primitive di osservabilità strutturata: `fair3.engine.logging.setup_logger`, mirroring di controllo JSON, metriche
  Scrittore JSONL, flag `--progress/--json-logs` a livello di CLI e documenti/test aggiornati che acquisiscono il nuovo
  flusso di lavoro.
- Regime Engine v2: `regime_probability`, controlli della serie di isteresi, CLI `fair3 regime` conartefatto
  persistenza (`probabilities.csv`, `hysteresis.csv`, `committee_log.csv`) e aggiornamenti di convalida per
  pesi di comitato/macro.
- Aggiornamenti del consenso di covarianza: mediana geometrica SPD opzionale (`sigma_spd_median`), flag CLI
  `--sigma-engine`, test delle proprietà PSD/ordinazione e documentazione aggiornata perstima
  pipeline.
- Motore dei vantaggi attesi con bootstrap di blocco: `block_bootstrap`, aiutanti di distribuzione EB, EB_LB
  test di monotonicità e aggiornamenti della documentazione per i guardrail di esecuzione.
- Execution & Tax IT v2: `size_orders` aggiornamento del dimensionamento dei lotti, scalare Almgren–Chriss
  helper, motore fiscale italiano(`compute_tax_penalty`, `MinusBag`) con cablaggio CLI
  `--tax-method` e documentazione/test aggiornati.
- Mappatura v2: beta rolling ridge con precedenti di segno, limiti di peso basati su CI80,
  governance degli errori di tracciamento per fattore, nuove sostituzioni CLI (`--te-factor-max`,
  `--tau-beta`), e test/documentazione estesi per i controlli di mappatura.
- Goal Engine v2: regime-aware Monte Carlo con contributi/riscatti programmati,
  glidepath adattivo, fan-chart mensile, CLI `fair3 goals --simulate`, output in
  `reports/`, e test aggiornati su schedule/glidepath.
- Reporting v2: metric fangrafici, valutazione del gate di accettazione, IC
  diagnostica di attribuzione, riepiloghi PDF, miglioramenti CLI e documentazione/test per il flusso di lavoro di reporting espanso
  .
- Mini GUI opzionale: `launch_gui`, comando `fair3 gui` con flag di percorso,
  fallback quando PySide6 manca, documentazione dedicata e test smoke con
  stub/assenza dipendenza.
- Ingest FRED esteso: default con curva Treasury 1-30Y, DTB3, CPI, breakeven
  5Y/10Y e TIPS 5Y/10Y, con test offline JSON/ZIP e documentazione aggiornata.
- Ingest Kenneth French: fetcher dedicato con fattorimensili, pacchetto 5x5,
  momentum e 49 industrie, parsing ZIP/TXT con normalizzazione long-form e
  documentazione/QA aggiornati.
- Ingest AQR: fetcher manuale/HTTP con mapping dichiarativo (QMJ, BAB, VALUE),
  scaling percentuale→decimale, gestione `manual://`, documentazione e test
  offline sui percorsi manuali.
- Ingest Alpha/q-Factors/Novy-Marx: fetcher misto CSV/HTML con percorsi manuali,
  scaling delle percentuali, integrazione CLI/documentazione e test dedicati.
- Ingest BIS REER/NEER: fetcher SDMX con simboli`<dataset>:<area>:<freq>`,
  normalizzazione `TIME_PERIOD`/`OBS_VALUE`, gestione `startPeriod` e aggiornamento
  della documentazione ingest/data.
- Ingest OECD CLI/PMI: fetcher SDMX (`OECDFetcher`) con parametri `contentType=csv`,
  `dimensionAtObservation=TimeDimension`, default CLI Italia/area euro, parser CSV
  resiliente e documentazione/registry aggiornati.
- Ingest World Bank: fetcher JSON con paginazione automatica, simboli normalizzati
  `<indicatore>:<ISO3>`, default popolazione/PIL Italia, metadati pagina nei log e
  documentazione aggiornata (README, ingest README, data catalog, roadmap, plan).
- Ingest CBOE: fetcher CSV (`CBOEFetcher`) per VIX/SKEW con guardia HTML, filtro
  `--from` post-download, simboli maiuscoli e documentazione/registry/plan
  aggiornati.
- Ingest Nareit: fetcher manuale (`NareitFetcher`) per gli indici FTSE Nareit
  Total Return (All Equity, Mortgage), parsing Excel locale con controllo
  colonne, data fine mese e aggiornamento documentazione/registry/plan.
- Ingest LBMA: fetcher HTML (`LBMAFetcher`) per i Fixing oro/argentodelle
  15:00 London, conversione USD→EUR via `ECBFetcher`, popolamento `pit_flag`
  alle 16:00 CET, documentazione/registry/plan aggiornati e test offline per
  parsing/FX fallback.
- Ingest Stooq: fetcher con normalizzazione `.us/.pl`, colonna `tz="Europe/Warsaw"`,
  cache in-process dei payload, documentazione aggiornata e suite offline per
  caching/filtro start/simboli upper-case.
- Ingest Yahoo fallback: `YahooFetcher` basato su `yfinance` con finestra
  massima di cinque anni, ritardo di due secondi configurabile, gestione della
  dipendenza opzionale e documentazione/test aggiornati.
- Ingest Alpha Vantage FX:`AlphaVantageFXFetcher` con throttling deterministico,
  sanitizzazione dell'URL (nessuna esposizione `apikey`), parsing CSV `FX_DAILY`
  e documentazione/test aggiornati su licenza e chiave API.
- Ingest Tiingo: `TiingoFetcher` con autenticazione tramite `TIINGO_API_KEY`,
  throttling deterministico, parsing JSON (`adjClose`/`close`), guardie HTML e
  aggiornamenti documentali/tests/registry.
- Ingest CoinGecko: `CoinGeckoFetcher` con endpoint`market_chart/range`,
  throttling minimo (1s), campionamento alle 16:00 CET con `pit_flag`, default
  `bitcoin`/`ethereum` e documentazione/tests/registry aggiornati.
- Ingest Binance Data Portal: `BinanceFetcher` per ZIP giornalieri`klines`,
  concatenazione multi-day con inferenza valuta quotata, gestione dei 404 con
  metadati `status` e aggiornamenti a documentazione/registry/test.
- Ingest Portfolio Visualizer references: `PortfolioVisualizerFetcher` per CSV mensili scaricati manualmente (US Total Stock Market, International Developed Market, US Total Bond Market, Gold Total Return) con scaling percentuale→decimale, directory `data/portfolio_visualizer_manual/` documentata e test su parsing/start/html/colonne.
- QA demo pipeline: comando`fair3 qa`, modulo `fair3.engine.qa`, artefatti deterministici (report mensile, robustezza, ablazione) e test/documentazione dedicati per audit end-to-end.
- Cleanup finale: README modulari per `fair3/`, CLI ed engine, docstring
  aggiornate per il modulo QA, screenshot concettuale della GUI in `docs/GUI.md`
  e chiusura roadmapPR-50 nel changelog/documentazione.

### Modificato
- Versione del pacchetto aumentata a `0.2.0` in `pyproject.toml` ed esposta la versione in `fair3.__init__` per l'introspezione del runtime.

### Note
- Questa versione costituisce la base per le PR PR-16 → PR-50 (regime v2, Σ SPD-median, bootstrap v2, esecuzione & tax v2,
  mapping v2, goal v2, reporting v2, ingest multi-fonte, mini GUI).
- Tutti i componenti restano marcati come anteprima: l'utilizzo è limitato a scopi educativi e di ricerca.
