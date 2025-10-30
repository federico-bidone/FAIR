# Piano PR-15

## Scope
- Porta il pacchetto FAIR-III a **v0.2.0** ed esponi la versione in `fair3.__init__`.
- Stabilisci l'impalcatura del repository per la roadmap v0.2: cartelle `data/raw/` e `data/clean/` monitorate, segnaposto di controllo,
  README/CHANGELOG aggiornamenti eAllineamento della roadmap.
- Allinea gli strumenti con la Guida allo stile di Google Python: configura `black` e `ruff` (controlli delle stringhe di documenti), semplifica gli hook di pre-commit,
  e assicurati che pytest venga eseguito automaticamente.

## Note di progettazione
- Centralizza la configurazione di lint/formato all'interno di `pyproject.toml` per evitare derive e applicare regole coerenti (limite di 100 colonne,
  convenzione docstring di Google, destinazione Python 3.11).
- Preserva seed deterministici tramite `audit/seeds.yml` e introduce `audit/checksums.json` come unica fonte di verità per i dati
  hash degli artefatti (inizialmente vuoti, da compilare in seguitoPR).
- Documentare la superficie di comando v0.2 e i limiti di conformità direttamente nel README in modo che i futuri contributori ereditino il framing UCITS/EU/IT
  prima di toccare il codice.

## Test e strumenti
- Il pre-commit deve eseguire `ruff`, `black` e `pytest` per rilevare linting/stile/testregressioni localmente su ogni commit.
- CI e sviluppatori eseguono: `ruff check .`, `black --check .`, `pytest -q`.
- Nessuna modifica al codice comportamentale viene introdotta in questo PR dell'impalcatura, ma i comandi di fumo (`fair3 --help`) dovrebbero rimanere inalterati.


# PR-18 Plan (Regime Engine v2)

## Ambito
- Sostituisci il comitato legacy con un comitato deterministicoImplementazione HMM/HSMM basata su `hmmlearn`.
- Estendi l'isteresi per supportare serie di attivazione/disattivazione ed esporre nuove manopole in `configs/thresholds.yml`.
- Fornire un comando CLI completo (`fair3 regime`) che carica il pannello pulito, persiste gli artefatti in `artifacts/regime/` ed emette metriche strutturate.

## Note di progettazione
- Introdurre `regime_probability(panel, cfg, seed)` la diagnostica dei componenti restituiti più la probabilità di crisi combinata; mantenere `crisis_probability` come wrapper di compatibilità.
- Crea un orchestratore di pipeline di regime (`fair3/engine/regime/pipeline.py`) che carica i pannelli Parquet o sintetizza dati deterministici quando mancano gli input.
- Guadagni CLI `--clean-root`, `--thresholds`, `--seed`, `--output-dir`, `--dry-run`, `--trace`; i parametri vengono emessi tramite `record_metrics`.
- `apply_hysteresis` ora applica i parametri di serie oltre alla permanenza/raffreddamento per evitare flip-flop.

## Test e strumenti
- I test unitari coprono i nuovi output del comitato, la sensibilità macro, le serie di isteresi, la generazione di artefatti della pipeline e il cablaggio CLI.
- I test delle proprietà garantiscono l'applicazione del raffreddamento con il nuovoparametri di serie.
- La documentazione (README, docs/VALIDATE.md, docs/roadmap.md, `fair3/engine/regime/README.md`) delinea il nuovo flusso di lavoro e le manopole.


# Piano PR-21 (Esecuzione e imposte IT v2)

## Ambito
- Aggiorna il dimensionamento dei lotti a lotti interi deterministici (`size_orders`) mantenendo
  `target_to_lots` per compatibilità con le versioni precedenti.
- Introdurre i costi Almgren–Chriss aggregati tramite `almgren_chriss_cost` eesporre
  FIFO/LIFO/min_tax tax match con loss carry a quattro anni (`MinusBag`).
- Estendi la CLI con `--tax-method` e documenta la pipeline di esecuzione più ricca.

## Note di progettazione
- Assicurati che `size_orders` convalidi le forme, gestisca prezzi zero/negativi o dimensioni dei lotti
  con garbo e rispecchi la formula Δw → lotti utilizzata a valle.
- Implementa `compute_tax_penalty` attorno agli input DataFrame in modo che il futuro controller
   possa collegare direttamente gli inventari degli strumenti; incapsula la gestione meno in
  `MinusBag` per il riutilizzo.
- Mantieni `tax_penalty_it` come wrapper leggero per euristiche rapide mentre le nuove
  classi di dati (`TaxRules`, `TaxComputation`) espongono informazioni di audit ricche.

## Test e strumenti
- Estendi `tests/unit/test_execution_primitives.py` per coprire `size_orders` e l'helper
  scalare Almgren–Chriss e proteggi il comportamento degli alias.
- Aggiungi test dedicati per `compute_tax_penalty` che coprono FIFO/LIFO/min_tax, meno
  consumo borse, acquisizione di nuove perdite ed errori di inventario insufficiente.
- Aggiorna la documentazione (README, docs/FAIR-III.md, docs/roadmap.md,
  `fair3/engine/execution/README.md`) e aggiorna il piano/CHANGELOG per contrassegnare
  PR-21 come completo.


# PR-22 Plan (Mapping v2)

## Ambito
- Estendere la stima del beta con segni a priori, limite di peso basato su CI80 e
  governance degli errori di tracciamento per fattore per stabilizzare le allocazioni degli strumenti.
- La CLI di superficie sostituisce i limiti TE per fattore e le soglie del CI beta.
- Perseverare una diagnostica riepilogativa più completa (larghezze CI beta, deviazione massima dei fattori)
  per il downstreampassaggi di controllo.

## Note di progettazione
- Rielaborazione `rolling_beta_ridge` per registrare i metadati e il supporto dell'applicazione
  dati a priori opzionali provenienti da `factor_index.long_sign`.
- Aggiungi `cap_weights_by_beta_ci` e `enforce_te_budget` aiutanti a livello di fattore in modo che
  la pipeline possa sequenzialmente ritagliare strumenti incerti e risolvere le esposizioni fattoriali
  prima della contrazione TE a livello di portafoglio.
- Aggiornare `run_mapping_pipeline` per collegare le nuove fasi di governance, onorareCLI
  sostituisce e scrive allocazioni normalizzate dopo il ritaglio ADV.

## Test e strumenti
- Estendi `tests/unit/test_mapping_beta.py` per l'applicazione dei segni e il nuovo
  c-beta scaler, più `tests/unit/test_mapping_te_budget.py` per morsetti a livello di fattore
  TE.
- Assicurarsi che CLI `fair3 map` accetti `--te-factor-max/--tau-beta` ed eseguire nuovamente lint
  + suite di unità per proteggere il comportamento deterministico.
- Aggiorna README, docs/FAIR-III.md, docs/roadmap.md e il registro delle modificheper contrassegnare
  PR-22 come consegnato.


# Piano PR-24 (Report v2)

## Ambito
- Estendi il modulo di reporting con grafici a ventaglio per metriche di ricchezza e rischio chiave,
  valutazione del gate di accettazione, diagnostica IC di attribuzione e dashboard PDF.
- Collega i nuovi artefatti nella CLI del report mensile e nelle classi di dati
  mantenendo la compatibilità con le versioni precedenti per i chiamanti esistenti.

## Note di progettazione
- Riutilizza i disegni bootstrap generati per il grafico a ventaglio della ricchezza percalcolare
  traiettorie Sharpe, MaxDD, CVaR, EDaR e CAGR; persistere le bande quantiliche come grafici
  PNG.
- Introdurre gli assistenti `acceptance_gates` e `attribution_ic` per la reportistica e il laboratorio di robustezza
  condividere la logica di governance; emettere il riepilogo dell'accettazione come JSON ed
  esporre la diagnostica IC per il QA downstream.
- Generare un PDF compatto (`reportlab`) combinando metriche, flag di conformità,
  gate di accettazione e artefatti grafici; arricchire `MonthlyReportArtifacts` con
  i nuovi percorsi.

## Testing & Tooling
- Estendere gli unit test per coprire i nuovi artefatti (fan chart metrici, accettazione
  JSON, generazione di PDF) e verificare i percorsi di bootstrap deterministici.
- Aggiungi copertura dedicata per `acceptance_gates`, `attribution_ic` e
  `plot_fanchart` percorsi di errore.
- Aggiorna README, documenti del modulo e CHANGELOG per descrivere il reporting espanso
  flusso di lavoro e output CLI.


# Piano PR-27 (acquisizione FREDestensione)

## Ambito
- Espandere le impostazioni predefinite del fetcher FRED per coprire le scadenze costanti del Tesoro (1 anno-30 anni),
  Buoni del Tesoro a 3 mesi, titoli CPI, inflazione di pareggio a 5 anni/10 anni e rendimenti reali TIPS a 5 anni/10 anni.
- Assicurati che il fetcher supporti sia i payload JSON che ZIP CSV per tutti i valori predefiniti con
  analisi deterministica, gestione NaN per i segnaposto ``."`` e filtro della data di inizio.
- Aggiornaimporta documentazione, cataloghi di origini dati e note del registro delle modifiche per riflettere
  la copertura predefinita più ricca per le funzionalità macro.

## Note di progettazione
- Mantieni invariata la convalida delle credenziali ma mostra la tupla estesa ``DEFAULT_SYMBOLS``
  per il riutilizzo da parte dei chiamanti CLI e della documentazione. L'ordine delle tuple rispecchia i tenori della curva
  preservare la leggibilità del controllo.
- Riutilizzare la logica di analisi ZIP esistente e rafforzare la copertura dell'unità per proteggere il set di simboli
  predefinito, il comportamento di esecuzione predefinita e la contabilità dei metadati.
- Aggiorna i documenti di acquisizione per elencare esplicitamente le serie predefinite in modo che gli operatori sappiano quali
  macro driver ottengono immediatamente quando eseguono ``fair3 ingest --source fred``.

## Test &Strumenti
- Aggiungi test unitari che asseriscono la tupla predefinita prevista e simulano un'esecuzione di recupero predefinita
  tramite download con patch scimmie, verificando la copertura dei simboli, la lunghezza dei metadati e il dtype
  normalizzazione.
- Riesegui ``ruff``, ``black``, and ``pytest`` e assicurati che i dispositivi offline utilizzino ancora il percorso di analisi
  ZIP per le esportazioni CSV.


# Piano PR-28 (Kenneth Frenchingest)

## Scope
- Introdurre una sottoclasse `FrenchFetcher` che scarica payload ZIP/TXT dal Kenneth
  R.Biblioteca di dati francese, che copre fattori di mercato, 2x3 a cinque fattori, momentum e portafogli settoriali 49
  .
- Normalizza i set di dati nello schema di acquisizione FAIR rimodellando i fattori in formato lungo,
  ridimensionando la percentuale in decimali e generando `<dataset>_<factor>`
  identificatori deterministici.
- Aggiorna acquisizione/README, cataloghi di dati e voci della roadmap in modo che gli operatori comprendano
  il nuovo universo predefinito e i vincoli di licenza (solo per uso didattico).

## DesignNote
- Estendi `BaseCSVFetcher` tramite un fetcher dedicato che impone download ZIP,
  rileva risposte HTML/limiti di velocità e deduce intestazioni quando viene definita la definizione del set di dati
  omette nomi di fattori espliciti (ad es. portafogli di settore).
- Fornire metadati del set di dati dichiarativi (`FrenchDataset`) per mantenere nome file, colonna
  selezione, ridimensionamento e gestione sentinella co-localizzati e testabili.
- Assicurarsi che la normalizzazione dei simboli sia deterministica e conforme allo stile di Google della denominazione,
  mentre vengono archiviati i metadati di controllo (licenza, URL, richieste) identici aaltri fetcher.

## Test e strumenti
- Aggiungi la copertura delle unità per l'analisi dei fattori di mercato e dei payload del settore, l'inferenza dell'intestazione,
  filtro della data di inizio e la contabilità dei metadati.
- Estendi i test CLI/registro in modo che `french` appaia in `available_sources()` e
  documenti le impostazioni predefinite nei documenti importati e in README.
- Esegui ``ruff``, ``black``, ``pytest`` offline per garantire un comportamento deterministico.

# Piano PR-29(Inserimento di set di dati AQR)

## Scope
- Implementa un `AQRFetcher` che ingerisca CSV Quality-Minus-Junk, Betting-Against-Beta,
  e Value factor inseriti manualmente in `data/aqr_manual/`, mantenendo la porta
  aperta per i download HTTP tramite metadati dichiarativi.
- Normalizza i set di dati nello schema di acquisizione FAIR (data/valore/simbolo) con
  data finale mensile deterministica e ridimensionamento da percentuale a decimale.
- Aggiorna la documentazione di acquisizione, le tabelle di dati README e la roadmap per documentare il
  flusso di lavoro manuale e i vincoli di licenza (“solo per uso didattico”).

## Note di progettazione
- Descrivi i metadati del set di dati con una classe di dati congelataacquisizione di nomi di file, data/valore
  colonne, ridimensionamento e URL opzionali in modo che sia possibile collegare nuove serie senza
  alterare il core del fetcher.
- Sostituisci `_download` per interpretare uno schema `manual://` personalizzato, visualizzando un utile
  `FileNotFoundError` quando gli utenti dimenticano di inserire il CSV, delegando al contempo i download standard
  HTTP a `BaseCSVFetcher` per l'automazione futura.
    - Proteggi dai payload HTML accidentali (ad esempio pagine di accesso o con limite di velocità) tramite
  controllando il payloadprefissi prima di analizzare e generare un `ValueError`.

## Testing e strumenti descrittivi
- Aggiungi unit test che creano directory manuali temporanee, scrivi CSV di esempio e
  convalida il dimensionamento, la normalizzazione della data, i metadati e gli output CSV.
- Copri i percorsi di errore per i file manuali mancanti e il rilevamento del payload HTML.
- Estendi i test di registro/importazione in modo che `aqr` venga visualizzato in `available_sources()` ed esegui
  `ruff`, `black` e `pytest` per mantenere la suite verde.


# Piano PR-31 (BIS REER/NEERingest)

## Ambito
- Implementare un `BISFetcher` che richieda serie REER/NEER dall'endpoint SDMX
  (`https://stats.bis.org/api/v1/data`) utilizzando i simboli dichiarativi `<dataset>:<area>:<freq>`
   (per impostazione predefinita sono `REER:USA:M` e `NEER:USA:M`).
- Normalizza i payload CSV nello schema di acquisizione FAIR (data/valore/simbolo),
  convertendo `TIME_PERIOD` in timestamp e forzando valori numerici mentre
  filtra le righe con formato errato.
- Aggiorna la documentazione di acquisizione, i cataloghi delle origini dati e la roadmap in modo che
  gli operatori comprendano il flusso di lavoro, le licenze e il manuale BISrequisiti.

## Note di progettazione
- Riutilizzo `BaseCSVFetcher` networking con helper di convalida più rigorosi che analizzano
  componenti di simboli, applicano prefissi ISO-3 e mappano le frequenze su
  `startPeriod` formattazione (mensile, trimestrale, annuale).
- Rafforzare il parser normalizzando le intestazioni (maiuscolo + carattere di sottolineatura), rifiutando HTML
  payload indicativi di limiti di velocità e mantenendo la dipendenza dall'implementazione
  libera.
- Messaggi di errore descrittivi della superficie quando manca il payload `TIME_PERIOD`o
  `OBS_VALUE` o quando l'utente trasmette simboli nel formato sbagliato.

## Testing e strumenti
- Aggiungi unit test che MonkeyPatch `_download` con dispositivi CSV, verificando l'avvio
  filtraggio, contenuto di metadati, coercizione di valori e rifiuto HTML.
- Estendi i test del registro per includere la nuova sorgente `bis` e mantieni gli elenchi CLI in sincronizzazione
  §
- Esegui `ruff`, `black` e `pytest` per verificare che il nuovo fetcher sia integratosenza
  regressioni.


# Piano PR-32 (acquisizione OCSE)

## Ambito
- Implementare un `OECDFetcher` che richieda serie CLI/PMI dall'endpoint SDMX
  (`https://stats.oecd.org/sdmx-json/data`) utilizzando simboli `<dataset>/<keys>` con
  copertura predefinita per l'indicatore anticipatore composito (Italia e area euro).
- Assicurarsi che il fetcher applichi parametri standard (`contentType=csv`,
  `dimensionAtObservation=TimeDimension`, `timeOrder=Ascending`) e supporti
  `startTime` filtro derivato dalla CLIargomenti.
- Aggiorna la documentazione di acquisizione, i cataloghi di dati, la roadmap e il registro delle modifiche mentre
  espone la nuova fonte tramite `available_sources()` e la CLI.

## Design Notes
- Dividi i percorsi dei simboli e le stringhe di query opzionali, unendo i parametri forniti dall'utente
  con quelli predefiniti tramite gli helper `urllib.parse` proteggendo al tempo stesso da percorsi
  vuoti.
- Normalizza le intestazioni CSV (maiuscolo + carattere di sottolineatura), accetta sia `TIME_PERIOD` che
  etichette di fallback (`TIME`, `DATE`) e tratta`OBS_VALUE`/`VALUE` come colonne di valori candidate
  .
- Rifiuta i payload HTML con messaggi `ValueError` espliciti in modo che i chiamanti possano riprovare
  o ricorrere normalmente.

## Test e strumenti
- Test unitari che coprono simboli predefiniti, composizione URL (`startTime`, parametri
  sostituzioni), analisi CSV e gestione degli errori per HTML o colonne mancanti.
- Estendi i test del registro per garantire che `oecd` appaia in `available_sources()`.
- Esegui `ruff`, `black` e`pytest` per mantenere deterministica la suite di acquisizione.


# Piano PR-33 (acquisizione della Banca Mondiale)

## Ambito
- Introdurre un `WorldBankFetcher` che utilizza l'API JSON v2, gestisce
  metadata di impaginazione (`page`, `pages`, `per_page`), e normalizza le serie nel
  formato FAIR (`date`, `value`, `symbol`).
- Supportare simboli multi-paese (`<indicatore>:<ISO3; ISO3>`) e impostare come
  default popolazione totale e PIL reale perl'Italia.
- Registrare sempre la licenza "World Bank Open Data Termini" e tracciare le
  richieste effettuate per ogni pagina.

## Design Notes
- Riutilizzare la serializzazione CSV del `BaseCSVFetcher` ma sovrascrivere il
  loop `fetch` per aggregare tutte le pagine JSON prima di applicare il filtro
  `--from`.
- Validare i payload: rifiutare HTML, convertire le stringhe numeriche dei
  metadati in interi, rimuovere valori nulli, comporre simboli come
  `<indicatore>:<ISO3>` sfruttando `countryiso3code`.
- Evitaredipendenze extra (niente `pandasdmx`): usare solo `json` della
  standard Library e `pandas`.

## Testing & Tooling
- Scrivere test unitari che verificano aggregazione multi-pagina, filtro `start`,
  gestione di simboli malformati e payload HTML.
- Estendere i test di registro/CLI per includere `worldbank` e verificare i
  simboli di default.
- Aggiornare README, docs/DATA.md, ingest README, roadmap e changelog conla
  nuova fonte Banca Mondiale.

## Piano PR-34 (CBOE VIX/SKEW ingest)

## Ambito
- Implementare `CBOEFetcher` con mapping dichiarativo dei file pubblici (`VIX_History.csv`, `SKEW_History.csv`) e guardia HTML per risposte di errore.
- Normalizzare i CSV in formato FAIR (`date`, `value`, `symbol`) mantenendo il simbolo maiuscolo, applicare il filtro `--from` post-download e loggarelicenza/URL.
- Aggiornare Registry/CLI/README/docs (tabella fonti) e aggiungere test unitari su parsing, filtro start e gestione di simboli non supportati.

## Design Notes
- Riutilizzare `_simple_frame` oppure parsing custom con dizionari di rinomina per gestire header differenti ("VIX Close", `SKEW`).
- Rifiutare payload HTML o simbolisconosciuti con `ValueError` descrittivi e mantenere licenza/URL nei metadati dell'`IngestArtifact`.
- Mantenere il simbolo maiuscolo nella colonna `symbol` per evitare mismatch con altre pipeline.

## Testing & Tooling
- Scrivere test unitari che MonkeyPatchano `_download` per VIX/SKEW, verificare filtro `--from`, licenza nei metadati e gestione errori HTML.
- Estendere i test di registro/CLI affinché `cboe` appaia in `available_sources()`.
- Aggiornare README, docs/DATA.md, ingest README, roadmap e changelogper documentare la nuova fonte e rieseguire `ruff`, `black`, `pytest`.

## PR-35 Plan (Nareit manual ingest)

## Scope
- Implementare `NareitFetcher` che legge gli Excel manuali (`NAREIT_AllSeries.xlsx`) con mapping dichiarativo di foglio, colonne escaling.
- Validare la presenza del file manuale, normalizzare date a fine mese e valori Total Return per All Equity e Mortgage REIT.
- Aggiornare Registry, CLI docs, README, roadmap, plan e changelog; predisporre la directory `data/nareit_manual/` nella documentazione.

## Design Notes
- Riutilizzare `SeriesSpec` con campi `sheet_name`, `date_column`, `value_column`, `frequency` per gestire future estensioni (trimestrale, altre serie).
- Usare `pandas.read_excel` con `BytesIO` per supportare payload manuali o HTTP; verificare colonne e scalare valori se espressi in percentuale.
- Documentare la licenza “for informational only” nei log/metadati e mantenere start filter post parsing.

## Testing & Tooling
- Creare test unitari che Monkeypatchano `_download` e `pd.read_excel` per ripristinare DataFrame sintetici, verificando filtro `--from` e licenza neimetadati.
- Testare l'errore `FileNotFoundError` quando l'Excel non è presente e `ValueError` per colonne mancanti.
- Estendere i test di registro/CLI affinché `nareit` compaia in `available_sources()` ed eseguire `ruff`, `black`, `pytest` prima del commit.

## PR-36 Plan (LBMA metals ingest)

## Scope
- Implementare `LBMAFetcher` che estrae le tabelle HTML dei Fixing Pomeridiani per oro e argento.
- Convertire i prezzi USD in EUR tramite i cambi BCE (serie `D.USD.EUR.SP00. A`) e impostare `pit_flag` quando l'orario corrisponde alle 16:00CET.
- Aggiornare registro, CLI docs, README, roadmap, plan e changelog; documentare la directory di output e la licenza LBMA.

## Design Notes
- Utilizzare `pandas.read_html` e selezionare la prima tabella con colonna `Date`, normalizzando eventuali header duplicati.
- Localizzare i timestamp a `Europe/London`, convertirli a `Europe/Rome` per il calcolo di `pit_flag`, quindi salvare l'istante inUTC senza fuso orario.
- Caricare i cambi USD/EUR da cache (`fx_rates`) o, se assenti, invocare `ECBFetcher` e memorizzare i risultati in `_fx_cache` con forward-fill per festività/weekend.

## Testing & Tooling
- Creare fixture HTML sintetiche con colonne `Date` e `USD (PM)` e MonkeyPatchare `_load_fx_rates` perrestituire cambi deterministici.
- Testare parsing positivo, rifiuto di payload HTML senza tabella, errore per simbolo sconosciuto e fallback FX mancante.
- Estendere i test di registro/CLI affinché `lbma` compaia in `available_sources()` ed eseguire `ruff`, `black`, `pytest` prima del commit.

## PR-37Plan (Stooq ingest hardening)

## Scope
- Rafforzare `StooqFetcher` con normalizzazione `.us/.pl`, colonna `tz="Europe/Warsaw"` e cache in-process dei payload.
- Aggiornare Registry, CLI docs, README, roadmap, plan e changelog per descrivere il nuovo comportamento.
- Garantire che il filtro `--from` continui a essere applicato post parsing e che i simboli siano esportati in maiuscolo.

## Design Notes
- Sovrascrivere `_download` per utilizzare un cache (dict) chiave→payload basato sul parametro `s`dell'URL.
- Normalizzare i simboli in minuscolo per la query e maiuscolo per l'output, mantenendo compatibilità con suffissi `.us`/`.pl`.
- Estendere `parse` per accettare `bytes`, validare header CSV, convertire i valori in `float` e aggiungere `tz` senza alterare l'ordinamentotemporale.

## Testing & Tooling
- Aggiornare i test offline (`tests/unit/test_stooq_fetcher_offline.py`) per verificare cache, filtro start e gestione HTML.
- Estendere i test di registro/CLI per assicurare la presenza della colonna `tz` e la normalizzazione del simbolo.
- Eseguire `ruff`, `black`, `pytest` prima del commit e registrare gli aggiornamenti documentali nelle sedi richieste.

## PR-38 Plan (Yahoo fallbackingest)

## Scope
- Implementare `YahooFetcher` come fallback basato su `yfinance`, rispettando una finestra massima di cinque anni e un ritardo di due secondi tra le richieste.
- Registrare la nuova sorgente nel registro e aggiornare README, docs/DATA.md, ingest README, roadmap, plan e changelog con note su licenza e dipendenzafacoltativo.
- Assicurare che il fetcher funzioni anche senza `yfinance` installato (errore esplicativo) e che l'utente possa ridurre il ritardo nei test.

## Design Notes
- Utilizzare uno schema pseudo `yfinance://<SYMBOL>?start=<ISO>` per propagare parametri e riutilizzare le infrastrutture esistenti di `BaseCSVFetcher`.
- Applicare `_clamp_start` per limitare l'intervallo, convertire le serie in CSV canonici (`date`, `value`) e inserire `time.sleep(delay_seconds)` solo dopo il download.
- Esporre `_import_yfinance` e`_now` come helper separati per facilitare i test; rilevare le colonne `Date`/`Close` o `Adj Close` restituite da `yfinance`.

## Testing & Tooling
- Aggiungere `tests/unit/test_yahoo_fetcher.py` per coprire URL, parsing, filtro start, applicazione finestra e mancanza di `yfinance`.
- Estendere `tests/unit/test_ingest_registry.py` per verificare la presenza dellasorgente `yahoo`.
- Aggiornare la documentazione e rieseguire `ruff`, `black`, `pytest` assicurandosi che i test saltino quando `yfinance` manca.

## PR-39 Plan (Alpha Vantage FX ingest)

## Ambito
- Implementare `AlphaVantageFXFetcher` per serie FX giornaliera (`function=FX_DAILY`) con coppie EUR (default: USD, GBP, CHF).
- Gestire la chiave API tramite parametro o variabile d'ambiente `ALPHAVANTAGE_API_KEY`, evitando che il valore compaia nei log/metadata.
- Applicare throttling deterministico (intervallo ≥12s) per rispettare il rate limit gratuito eTrasformare gli errori JSON (`Note`, `Error Message`) in eccezioni leggibili.

## Design Notes
- Costruire URL sanitizzati senza `apikey`, aggiungendo il parametro solo in `_download` prima della chiamata HTTP.
- Supportare formati di simbolo `AAA`, `AAA/BBB` e `AAABBB`, assumendoEUR come controvaluta quando non specificata.
- Riutilizzare `_simple_frame` per normalizzare il CSV (`timestamp`, `close`) e filtrare `start` post-download; rilevare il payload HTML/JSON per la segnalazione del limite di velocità.

## Testing & Tooling
- Aggiungere `tests/unit/test_alphavantage_fetcher.py` con casi su parsing CSV, rate limit JSON, throttling, mascheramento URL e simboli invalidi.
- Estendere `tests/unit/test_ingest_registry.py` e la documentazione (README, docs/DATA.md, ingest README, roadmap, changelog) con la nuova sorgente.
- Rieseguire`ruff`, `black`, `pytest`; nei test impostare `throttle_seconds=0` per evitare attese artificiali.

## PR-40 Plan (Tiingo ingest)

## Scope
- Implementare `TiingoFetcher` per prezzi daily equities/ETF via endpoint `https://api.tiingo.com/tiingo/daily/<symbol>/prices`.
- Richiedere `TIINGO_API_KEY` (parametro o env var) e applicare throttling deterministico perrispettare il contratto API.
- Normalizzare il payload JSON (`adjClose`/`close`) nel formato FAIR (`date`, `value`, `symbol`) e gestire payload HTML o colonne mancanti.

## Design Notes
- Costruire URL sanificati includendo `startDate` quando il CLI fornisce `--from`; evitare di loggare la chiave API nei metadati.
- Implementare `_download` personalizzato con header `Authorization: Token <key>` e retry/backoff come nel `BaseCSVFetcher`.
- Riutilizzare `pandas` per convertire la lista JSON in DataFrame, selezionare `adjClose` (fallback `close`), convertire le date a UTC e rimuovere osservazioninulle.

## Testing & Tooling
- Creare `tests/unit/test_tiingo_fetcher.py` coprendo URL, chiave mancante, parsing JSON, payload HTML e registrazione nel registro.
- Aggiornare `tests/unit/test_ingest_registry.py` per includere `tiingo` e documentazione (README, docs/DATA.md, ingest README, roadmap, changelog).
- Rieseguire `ruff`, `black`, `pytest` assicurandosi che i test saltino correttamente quando le dipendenze opzionali non sono presenti.

## PR-41 Plan (CoinGecko ingest)

## Scope
- Implementare `CoinGeckoFetcher` basato sull'endpoint `coins/<id>/market_chart/range` con Throttle deterministico e campionamento alle16:00 CET.
- Normalizzare i dati in EUR, aggiungere `currency` e `pit_flag`, garantire default (`bitcoin`, `ethereum`) e gestione errori (HTML, payload `error`).

## Design Notes
- Costruire URL con `from`/`to` derivatida `start` (UTC) e `now_fn` iniettato per i test; default a cinque anni indietro quando `start` è assente.
- Applicare throttling tramite `time.monotonic`, calcolare il punto giornaliero più vicino a 15:00 UTC (16:00 CET) e impostare `pit_flag=1` se la differenza è ≤15 minuti.
- Restituire DataFrame con colonne `date`, `value`, `symbol`, `currency`, `pit_flag` ordinate cronologicamente.

## Testing & Tooling
- Creare `tests/unit/test_coingecko_fetcher.py` per verificare campionamento, `pit_flag`, licenza, gestione errori e costruzione URL (inclusi default di 5anni).
- Aggiornare `tests/unit/test_ingest_registry.py` e la documentazione (README, docs/DATA.md, ingest README, roadmap, changelog) con la nuova sorgente.
- Rieseguire `ruff`, `black`, `pytest` garantendo che l'acceleratore sia disattivabile nei test(`delay_seconds=0`).

## PR-42 Plan (Binance Data Portal ingest)

## Scope
- Implementare `BinanceFetcher` per scaricare i file ZIP giornalieri `data/spot/daily/klines/<symbol>/<interval>/` con default `BTCUSDT`.
- Normalizzare le colonne open/high/low/close/volume, derivare la valuta quotata e valorizzare `pit_flag`/`tz` nei DataFrame restituiti.
- Supportare `--from` e `--symbols`, gestire intervalli mancanti (404) con log e metadati dedicati, mantenendo l'intervallo massimo a 365 giorni quando `start` èassente.

## Design Notes
- Riutilizzare `_download` personalizzato per restituire bytes ZIP e decomprimere in memoria selezionando il membro CSV deterministico.
- Iterare sui giorni con `tqdm` opzionale, annotando `status` (`ok`/`missing`) per ciascuna richiesta nei metadati e filtrando le date in UTC naivedopo la concatenazione.
- Derivare la valuta quotata tramite suffissi noti (USDT, BUSD, EUR, ecc.) con fallback `UNKNOWN`; assicurare che i log riportino licenza e intervallo richiesto.

## Testing & Tooling
- Aggiungere `tests/unit/test_binance_fetcher.py` per coprire parsing ZIP, concatenazione multi-day, gestione dei 404 e rifiuto dei payload HTML.
- Estendere `tests/unit/test_ingest_registry.py` e la documentazione (README, docs/DATA.md, ingest README, roadmap, changelog) con la sorgente `binance`.
- Rieseguire `ruff`, `black`, `pytest`; nei test utilizzare payload sintetici in-memory per evitare chiamate di rete.

## PR-43 Plan (Portfolio Visualizer references ingest)

## Scope
- Implementare `PortfolioVisualizerFetcher` per CSV mensili scaricati da Portfolio Visualizer (US Total Stock Market, International Developed Market, US Total Bond Market, Gold Total Return).
- Normalizzare i file nel formato FAIR(`date`, `value`, `symbol`) scalando automaticamente la colonna `Return` e allineando le date a fine mese.
- Documentare la directory manuale `data/portfolio_visualizer_manual/`, registrare la sorgente `portviz` nel registro/CLI e aggiornare README, docs/DATA.md, roadmap e changelog.

## Design Notes
- Definire una dataclass `PortfolioVisualizerDataset` per mantenere dichiarativa la configurazione dei dataset (filename, colonne, scala, frequenza, eventuale rename).
- Gestire lo schema `manual://` in `_download` e produrre messaggi d'errore chiari per file mancanti o payload HTML.
- Applicare `MonthEnd(0)` ai dataset previste e prevedere il campo `rename` per supportare futurialias dei simboli Portfolio Visualizer.

## Testing & Tooling
- Aggiungere `tests/unit/test_portfolio_visualizer_fetcher.py` con casi su parsing positivo, filtro `start`, assenza file, colonne mancanti e payload HTML.
- Aggiornare `tests/unit/test_ingest_registry.py` per includere `portviz` e rieseguire `ruff`, `black`, `pytest` assicurando il determinismo della suite.
- Esplicitare nella documentazione ingest la licenza “Portfolio Visualizer — informational/educational use” e i passaggi per popolari `data/portfolio_visualizer_manual/`.
