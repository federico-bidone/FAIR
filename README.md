# FAIR-III (Unified) Portfolio Engine

> Strumento informativo/didattico; non costituisce consulenza finanziaria o raccomandazione.

> **Solo didattico** — Questo repository fornisce un'implementazione di ricerca e apprendimento del quadro di costruzione del portfolio FAIR-III.**Non** è una raccomandazione di investimento, una promozione finanziaria o una consulenza personalizzata ai sensi della MiFID II.

## Panoramica
FAIR-III (Unified) è uno stack di ricerca di portafoglio basato esclusivamente su Windows e Python che acquisisce dati macro e di mercato gratuiti (BCE, FRED, BoE, Stooq, French Data Library, BRI, OCSE, Banca Mondiale, CBOE, Nareit, LBMA, Yahoo fallback tramite yfinance), creapannelli puntuali, stima i rendimenti attesi e le matrici di covarianza, costruisce allocazioni basate sui fattori con forti vincoli di implementabilità al dettaglio e produce esecuzioni verificabili e artefatti di reporting. Il sistema enfatizza la parsimonia, la replicabilità e il rispetto dei vincoli UCITS/UE/IT, tra cui seeding deterministico, audit trail e gestione realistica di costi/tasse.

### Caratteristiche principali
-  Pipeline deterministica e verificabile con gestione centralizzata del seed e registrazione del checksum.
- CLI pipeline (`fair3 factors`, `fair3 estimate`, `fair3 optimize`, `fair3 map`) orchestrare
  generazione di fattori attraverso la mappatura degli strumenti mentre si acquisiscono automaticamente istantanee di audit.
- Stima complessiva della media/varianza con la fusione Black-Litterman e fallback quando i rapporti di informazione sono insufficienti.
- Generatori di allocazione dei fattori (Max-Sharpe, HRP, DRO, CVaR-ERC) combinati da un meta-discente che penalizza il turnover e il tracking error.
- Mappatura dalle allocazioni dei fattori agli strumenti con beta rolling ridge, HRP intra-fattore e limiti di liquidità/ADV.
- Sovrapposizione del regime utilizzando un comitato di segnali con isteresi e controlli di raffreddamento.
- Livello di esecuzione con dimensionamento dei lotti, costi di transazione Almgren–Chriss, euristica fiscale italiana e garanzie di non scambio.
- Report mensili con grafici a ventaglio, gate di accettazione, dashboard PDF, laboratorio di robustezza (bootstrap/replay), studi di ablazione e artefatti di audit completi.
- Motore Monte Carlo basato su obiettivi che produce probabilità di successo consapevoli del regime e artefatti del glidepath.
- GUI PySide6 opzionale con gestione delle API key, scoperta dell'universo
  investibile e ingest automatico dei provider suggeriti.

## Installazione (Windows 11)
1. Installa Python 3.11 (64 bit) da Microsoft Store o python.org e assicurati che `python` punti a 3.11.
2. Apri **PowerShell** e imposta i criteri di esecuzione se necessario: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`.
3. Clona il repository e crea un ambiente virtuale:
   ```powershell
   python -m venv .venv
   . .venv/Scripts/Activate.ps1
   pip install -e .[dev,gui]
   pre-commit install
   ```
4. Conferma ilconfigurazione:
   ```powershell
   ruff check .
   black --check .
   pytest -q
   ```

## Novità nella v0.2
- Versione aumentata a **0.2.0** con impalcatura del repository per le tappe fondamentali di FAIR-III v0.2 (regime v2, Σ SPD-mediana, bootstrap v2,
  esecuzione e imposte v2, mappatura v2, obiettivi v2, reporting v2, acquisizione multi-sorgente, mini GUI opzionale).
- Configurazione deterministica centralizzata tramite `audit/seeds.yml` e registro checksum segnaposto in `audit/checksums.json`.
- Layout data lake preparato con cartelle tracciate `data/raw/` e `data/clean/` per artefatti PIT (Parquet + SQLite).
- Strumenti allineati alla Google Python Style Guide: `black` con limite di 100 colonne, `ruff` con controlli delle stringhe di documentazione di Google e
  hook pre-commit che eseguono lint, formattatori e pytest.
- README aggiornato con Quickstart v0.2, tabella di riferimento CLI, promemoria di conformità UCITS/UE/IT e suggerimenti per la configurazione deterministica.

## Quickstart v0.2
Esegui la CLI end-to-end su un computer con accesso a Internet per i datidownload. Ciascun comando registra l'attività in `artifacts/` e controlla i metadati in `artifacts/logs/`.

```powershell
python -m venv .venv
. .venv/Scripts/activate  # su Windows; usa 'source .venv/bin/activate' su Linux/Mac
pip install -e .[dev,gui]
pre-commit install

fair3 validate
fair3 ingest --source ecb --from 1999-01-04
fair3 ingest --source fred --symbols DGS10 T10YIE CPIAUCNS
fair3 etl --rebuild
fair3 factors --validate --oos-splits 5
fair3 estimate --cv-splits 5 --sigma-engine spd_median
fair3 optimize --generators A, B, C, D --meta
fair3 map --hrp-intra --adv-cap 0.05 --te-factor-max 0.02 --tau-beta 0.25
fair3 regime --dry-run --trace
fair3 execute --rebalance-date 2025-11-01 --dry-run --tax-method min_tax
fair3 report --period 2025-01:2025-11 --monthly
fair3 goals --simulate
fair3 gui
fair3-gui
```

Configura eventuali credenziali richieste dai data provider dal pannello
**API key** della GUI: le chiavi vengono cifrate nel keyring del sistema
operativo e replicate automaticamente nella sessione. Per ambienti headless è
possibile popolare le credenziali tramite `keyring set fair3:<servizio> default`.

## Riferimento comandi CLI (v0.2)
Tutti i comandi accettano `--progress/--no-progress` per attivare/disattivare le barre tqdm e `--json-logs/--no-json-logs` per eseguire il mirroring dell'audit strutturato
log.
| Comando | Scopo | Opzioni chiave |
| --- | --- | --- |
| `fair3 validate` | Convalida gli schemi di configurazione YAML prima di eseguire la pipeline. | `--verbose`, `--json-logs`, `--no-progress` |
| `fair3 ingest` | Scarica i dati grezzi in `data/raw/` con registrazione di controllo completa. | `--source`, `--symbols`, `--from`, `--throttle`, `--dry-run` |
| `fair3 universe` | Unifica universi broker, arricchisce gli ISIN con OpenFIGI e suggerisce i provider dati. | `--brokers`, `--output-dir`, `--openfigi-key`, `--dry-run` |
| `fair3 etl` | Costruisci pannelli PIT Parquet/SQLite da artefatti grezzi acquisiti. | `--rebuild`, `--dry-run`, `--json-logs` |
| `fair3 factors` | Libreria di fattori di calcolo con suddivisioni di convalida e report QA. | `--validate`, `--oos-splits`, `--dry-run` |
| `fair3 estimate` | Stima μ/Σ utilizzando motori ensemble e PSD/SPD. | `--cv-splits`, `--sigma-engine`, `--dry-run` |
| `fair3 optimize` | Esegui generatori di allocazioni e meta-mix con penalità TO/TE. | `--generators`, `--meta`, `--dry-run` |
| `fair3 map` | Mappare i pesi dei fattori sugli strumenti con protezioni β. | `--hrp-intra`, `--adv-cap`, `--te-factor-max`, `--tau-beta`, `--dry-run` |
| `fair3 regime` | Calcola le probabilità di crisi con HMM/comitato. | `--clean-root`, `--thresholds`, `--seed`, `--dry-run`, `--output-dir`, `--trace` |
| `fair3 execute` | Dimensionamento degli ordini, applicazione dei costi ed euristica fiscale italiana. | `--rebalance-date`, `--tax-method`, `--dry-run` |
| `fair3 report` | Produci dashboard mensili PDF/CSV con gate di accettazione. | `--period`, `--monthly`, `--dry-run` |
| `fair3 goals` | Esegui Monte Carlo consapevole del regime con la guida del glidepath. | `--simulate`, `--dry-run`, `--json-logs` |
| `fair3 gui` / `fair3-gui` | Avvia la GUI di orchestrazione PySide6 opzionale. | `--dry-run`, `--raw-root`, `--clean-root`, `--artifacts-root`, `--audit-root`, `--thresholds`, `--params`, `--goals`, `--report`, `--universe-dir`, `--reports-dir`, `--secrets-path` |
| `fair3 qa` | Esegui la pipeline demo deterministica del QA ed emetti artefatti di controllo. | `--label`, `--output-dir`, `--start`, `--end`, `--draws`, `--block-size`, `--cv-splits`, `--validate-factors`, `--seed` |

## GUI opzionale (PySide6)
Installa l'extra `gui` per abilitare l'orchestratore grafico e i relativi binding:

```bash
pip install .[gui]
```

Avvia l'interfaccia con `fair3 gui` (o con lo shortcut `fair3-gui`). Le schede
principali offrono:

- **Ingest:** selezione della sorgente, simboli opzionali e modalità automatica che
  riutilizza la mappatura dell'universo investibile.
- **Automation:** esegue `run_universe_pipeline`, mostra i provider suggeriti e
  lancia l'ingest multi-provider utilizzando i ticker arricchiti da OpenFIGI.
- **Pipeline:** shortcut per ETL, fattori, stima, mappatura, regime e obiettivi.
- **Reports:** genera report mensili in `data/reports/monthly`, aggiorna la lista
  dei PDF e apre il file selezionato nel visualizzatore di sistema.
- **API key:** salva le credenziali nel keyring locale, mascherandole nei log e
  sincronizzando le variabili d'ambiente per la sessione corrente.

Quando PySide6 non è installato `launch_gui` emette un log informativo ed esce
senza errori, preservando il funzionamento della CLI in ambienti headless.

## Guardie di conformità UCITS/UE/IT
- **Universo:** limita i portafogli a ETF/futures conformi agli OICTS per gli investitori al dettaglio dell'UE; traccia i metadati KID in `instrument`.
- **Tasse:** applica il regime fiscale italiano (26% plusvalenze, 12, 5% pro-rata sui governi ≥51%, 0, 2% imposta di bollo, compensazione delle perdite quadriennali).
- **Point-in-time:** ogni set di dati, funzionalità e panel deve rispettare l'allineamento PIT ed evitare distorsioni look-ahead con ritardi appropriati.
- **Valuta:** memorizza i valori nella base EUR, utilizzando FX BCE a16:00; acquisisci il fuso orario originale e i metadati della licenza per riga.
- **Controllabilità:** conserva seed deterministici, acquisisci checksum e opzioni di prova CLI per dimostrare l'idoneità alla conformità.

`fair3 factors` ora scrive pannelli di fattori deterministici (`artifacts/factors/*.parquet`),
diagnostica di convalida e metadati (inclusa la governance dei segni economici).`fair3 estimate`
produce consenso `mu_post.csv`, `sigma.npy` e mescola/deriva i log in
`artifacts/estimates/` mentre copia la configurazione e le istantanee seed in
`artifacts/logs/`.`fair3 optimize` memorizza i CSV specifici del generatore, l'allocazione mista,
e la diagnostica ERC all'interno di `artifacts/weights/`.`fair3 map` traduce le ponderazioni dei fattori in
esposizioni strumentali con beta mobili, fasce CI80, riepiloghi di tracking error e liquidità
aggiustamenti persistenti in `artifacts/mapping/` e `artifacts/weights/`.

Per sottoporre a stress test le ultime allocazioni end-to-end, eseguire il test deterministicoQA
pipeline:

```bash
fair3 qa --label demo --draws 256 --block-size 45
```

Il comando sintetizza un set di dati PIT, esegue ETL → fattori → stime →
ottimizza → mappa → regime → report e infine esegue il laboratorio di robustezza con
ablazione. Gli artefatti vengono scritti in `artifacts/qa/<label>/` (o nella directory
fornita tramite `--output-dir`) tra cui:

- Report PDF mensile con porte di accettazione (`reports/<period>/monthly_report.pdf`).
- `robustness/robustness_report.pdf`, `summary.json` e `ablation.csv`.
- Istantanee di controllo(`audit/`) acquisizione di seed, configurazioni e checksum.

`fair3 execute` attualmente presenta la ripartizione delle decisioni deterministiche (deriva,
EB_LB, costo, imposta) senza inviare ordini.`fair3 report --period
... --monthly` emette riepiloghi CSV/JSON deterministici e grafici PNG all'interno
`artifacts/reports/<period>/`; i dispositivi sintetici supportano la CLI finché la pipeline
completa completa collega gli artefatti PIT reali attraverso il livello di reporting.`fair3 goals`
legge `configs/goals.yml`/`configs/params.yml`, esegue una simulazione Monte Carlo
 compatibile con il regime e scrive `summary.csv`, `glidepath.csv`, e un PDF in
`reports/` (o directory custom) per verificare le probabilità
di successo.

## DataFonti e licenze
| Fonte | Copertura | Note |
| --- | --- | --- |
| BCE | Tassi macroeconomici dell'area euro | Utilizza l'endpoint CSV REST SDW con licenza/URL registrati per richiesta. |
| FRED | Macro/mercato USA | Interfaccia CSV pubblica (`fredgraph.csv`) senza chiave API; dati mancanti forzati a NaN. |
| OCSE | Indicatori anticipatori, PMI, macro compositi | Endpoint SDMX (`stats.oecd.org/sdmx-json/data`) richiesto come CSV con `dimensionAtObservation=TimeDimension`. |
| Banca d'Inghilterra | Tariffe, stato patrimoniale | Interfaccia di download CSV (`_iadb-getTDDownloadCSV`) con attribuzione registrata. |
| BRI | Tassi di cambio effettivi reali/nominali | Endpoint CSV SDMX (`/api/v1/data/REER`) con arrotondamento `startPeriod` e protezioni del limite di velocità. |
| CBOE | Indici di volatilità (VIX) e SKEW | Download CSV diretto (`cdn.cboe.com/api/global/us_indices/daily_prices`) con guardrail HTML e avviso di licenza. |
| LBMA | Correzione PM oro e argento (convertito in EUR) | Tabelle HTML recuperate alle 15:00 di Londra, convertite in EUR tramite FX della BCE con `pit_flag` alle 16:00 CET. |
| Nareit | Indici FTSE Nareit REIT (mensili) | Eliminazione manuale di Excel (`data/nareit_manual/NAREIT_AllSeries.xlsx`) analizzata tramite `fair3 ingest --source nareit`; licenza “solo a scopo informativo”. |
| Visualizzatore portfolio (manuale) | Riferimenti di asset class sintetiche (mensile) | Il CSV manuale viene inserito in `data/portfolio_visualizer_manual/` analizzato tramite `fair3 ingest --source portviz`; solo uso didattico/informativo. |
| PortfolioCharts Simba (manuale) | Compositi obbligazionari e stile azionario USA (mensile) | Cartella di lavoro Excel manuale `data/portfoliocharts/PortfolioCharts_Simba.xlsx` analizzata tramite `fair3 ingest --source portfoliocharts`; solo uso didattico/informativo. |
| Curvo.eu (manuale) | Backtest azionari/obbligazionari di OICVM europei (giornalieri) | Il CSV manuale scende in `data/curvo/` più file FX BCE `fx/<CCY>_EUR.csv`; `fair3 ingest --source curvo` calcola il rendimento totale in EUR con licenza “solo uso informativo/didattico”. |
| Dati storici EOD / backtes.to | Prezzi EOD mensili (API/manuale) | CSV manuali in `data/eodhd/` (es. `SPY.US.csv`) o chiamate API a `https://eodhistoricaldata.com/api/eod/<symbol>?period=m&fmt=json` con `EODHD_API_TOKEN`; licenza "Dati storici EOD - API commerciale; estratti manuali da backtes.to (solo per uso didattico)". |
| Stoq | Indici di mercato, FX | Feed CSV giornaliero (`q/d/l`) con normalizzazione `.us/.pl`, memorizzazione nella cache in-process e metadati del fuso orario. |
| Yahoo (ripiego) | Chiusure rettificate azioni/ETF | Richiede `yfinance` opzionale; limitato a un periodo di cinque anni con accelerazione di due secondi e avviso di licenza per uso personale. |
| RQA (manuale) | Fattori (QMJ, BAB, VALORE) | Drop manuale del CSV in `data/aqr_manual/`; la licenza richiede solo uso didattico. |
| Alfa / Fattori q / Novy-Marx | Qualità, redditività, spread di valore | HTTP CSV (Alpha Architect, q5) con HTML drop manuale in `data/alpha_manual/` per le tabelle Novy-Marx; licenza solo per uso didattico. |
| Alpha VantageFX | Cross giornalieri FX EUR (USD, GBP, CHF) | REST API `function=FX_DAILY` (`ALPHAVANTAGE_API_KEY` env var) con throttling automatico (5 chiamate/min) e normalizzazione CSV. |
| Tiingo | Chiusure rettificate azioni/ETF | Richiede `TIINGO_API_KEY`; Endpoint JSON REST (`/tiingo/daily/<symbol>/prices`) con intestazione di autorizzazione e limitazione deterministica. |
| CoinGecko | Prezzi spot delle criptovalute (EUR) | Endpoint REST `coins/<id>/market_chart/range` campionato alle 15:00 UTC (16:00 CET) con accelerazione di un secondo e segnalazione PIT. |
| Portale dati Binance | Kline spot crittografiche (1d/1h) | Archivi ZIP giornalieri `data/binance.vision/data/spot/daily/klines/<symbol>/<interval>/<symbol>-<interval>-<date>.zip` analizzati con metadati delle valute quotate e guardrail di ridistribuzione. |
| Banca Mondiale | Indicatori macro (PIL, popolazione, debito) | API JSON (`api.worldbank.org/v2/country/<ISO3>/indicator/<series>`) con impaginazione automatica e simboli normalizzati ISO3. |

Ogni esecuzione di `fair3 ingest` produce file CSV timestampati (`<source>_YYYYMMDDTHHMMSSZ.csv`) con colonne standard (`date`, `value`, `symbol`) salvati in `data/raw/<source>/`.Le informazioni di licenza e gli URL vengono registrati nei log rotanti sotto `artifacts/logs/` per supportare la conformità UCITS/EU/IT.Il passo ETL ricostruisce un pannello PIT salvando `asset_panel.parquet` in `data/clean/` (campo `field` con valori `adj_close`, `ret`, `lag_*`, ecc.) e il QA log in `audit/qa_data_log.csv`.Non ridistribuire set di dati di terze parti senza autorizzazione.

## Concetti fondamentali
- **Stima μ/Σ:** I rendimenti attesi provengono da un insieme di riduzione a zero + bagging OLS + gradient boosting impilati tramite ridge e miscelati con le viste Black–Litterman (ω:=1 fallback quando IR<τ).Le covarianze combinano Ledoit–Wolf, lazo grafico e fattore di contrazione; l'utente può scegliere tra il consenso PSD (mediana elemento per elemento + Higham) o la mediana geometrica SPD (`--sigma-engine spd_median`).
- **Protezioni dalla deriva Σ:** Frobenius relativo e la diagnostica di correlazione massima attivano cancelli di accettazione e sovrapposizioni di esecuzione quando emergono rotture strutturali.
- **Black–Litterman fallback:** Le visualizzazioni si fondono con l'equilibrio a meno che il rapporto delle informazioni sulla visualizzazione non scenda al di sotto di `τ_IR=0.15`, nel qual caso il sistema ritorna all'equilibrio di mercato (ω=1).
- **Proiezione PSD di Higham:** Assicura che le matrici di covarianza rimangano semi-definite positiveprima dell'ottimizzazione.
- **Parità gerarchica del rischio (HRP):** Fornisce allocazioni di base diversificate e distribuzione intra-fattore.
- **CVaR / EDaR:** Vincoli e obiettivi di rischio finale espressi in orizzonti mensili (CVaR 95%) e triennali (EDaR).
- **Ottimizzazione distribuzionalmente robusta (DRO):** Penalizza le allocazioni da parte di Wassersteinraggio ρ per evitare errori di stima.
- **Stack dei fattori macro:** Dieci premi macro deterministici (mercato, momentum, inversione, valore, carry, qualità, difensivo, liquidità, crescita, inflazione, tassi) prodotti tramite spread quantili con validazione CP-CV/DSR/FDR e controlli di ortogonalità.
- **Inclinazione del regime:** Un comitato (HMM gaussiano a due stati, stress di volatilità, rallentamento macro)produce probabilità di crisi che guidano un parametro di inclinazione λ con isteresi (on=0, 65, off=0, 45, dwell=20 giorni, cooldown=10 giorni).
- **Mappatura da fattore a strumento:** i beta Rolling Ridge con limiti bootstrap alimentano HRP intrafattoriale, budget di errore di tracciamento e dimensionamento delle operazioni basato su ADV.
- **Liquidità e conformità:** Budget di errore di tracciamento, limiti di turnover e vincoli ADV/dimensioni del lotto garantiscono l'implementazione al dettaglio.
- **Regola di non scambio:** Le transazioni vengono eseguite solo quando vengono superate le bande di deriva **e**il bootstrap a blocchi EB_LB meno costi e tasse rimane positivo.
- **Report mensile:** aggrega gli artefatti PIT in riepiloghi CSV/JSON pronti per la conformità, attribuzione di fattori/strumenti, dashboard fatturato/costo, diagnostica del gate di accettazione, grafici a ventaglio metrici e istantanee PDF archiviati in `artifacts/reports/<period>/`.
- **Laboratorio di robustezza e ablazione:** Bootstrap a blocchi(60 giorni) e shock stilizzati (1973, 2008, 2020, stagflazione) valutano i cancelli di accettazione; i comandi di governance vengono eseguiti tramite il cablaggio di ablazione per documentare il sollevamento di PSD, fallback BL, trigger di deriva, meta TO/TE, inclinazione del regime e regola di non scambio.
- **Pianificazione basata sugli obiettivi:** la simulazione Monte Carlo unisce regimi di base/crisi con glidepath deterministici e programmi di contribuzione, emettendo probabilità di successo ponderate e dashboard PDF in `reports/`.

## Layout del repository
```
pyproject.toml
README.md
LICENSE
PLAN.md
.pre-commit-config.yaml
.github/
  workflows/ci.yml
  ISSUE_TEMPLATE/
  PULL_REQUEST_TEMPLATE.md
CODEOWNERS
SECURITY.md
CONTRIBUTING.md
docs/
configs/
audit/
  seeds.yml
  checksums.json
data/
  raw/
  clean/
artifacts/
fair3/
  cli/main.py
  engine/
    ingest/
    etl/
    factors/
    estimates/
    allocators/
    mapping/
    regime/
    execution/
    goals/
    reporting/
    robustness/
    utils/
tests/
```
Ogni motoreil sottomodulo verrà fornito con le proprie API README dettagliate, l'utilizzo della CLI, gli errori comuni e i flag di tracciabilità man mano che la funzionalità arriva nelle tappe successive. Il piano dettagliato degli interventi è consultabile in [`docs/roadmap.md`](docs/roadmap.md) mentre la guida all'osservabilità vive in [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md).

### Guida al modulo
La tabella seguente riassume i pacchetti più importanti affinché i nuovi contributori possano orientarsi rapidamente:

| Pacchetto | Scopo | Punti di ingresso chiave |
| --- | --- | --- |
| `fair3.cli` | Definizioni dell'interfaccia della riga di comando e analisi degli argomenti. | `fair3/cli/main.py` orchestra sottocomandi come `fair3 factors` o `fair3 optimize`. |
| `fair3.engine.ingest` | Downloader per fonti BCE, FRED, BoE, BRI, OCSE, Banca Mondiale, CBOE, Nareit, LBMA, Stooq, French Data Library e Yahoo fallback (yfinance) con dispositivi offline. | `run_ingest` pipeline, classi fetcher come `FREDFetcher`, `YahooFetcher`. |
| `fair3.engine.universe` | Aggregatore degli universi investibili dei broker, arricchiti con mapping OpenFIGI e scelta intelligente dei data provider. | `run_universe_pipeline`, fetcher `TradeRepublicFetcher`, comando `fair3 universe`. |
| `fair3.engine.etl` | Costruzione di pannelli puntuali e utilità di pulizia TR. | `TRPanelBuilder`, CLI ETL richiamata tramite `fair3 etl`. |
| `fair3.engine.factors` | Libreria di fattori, ortogonalizzazione, cablaggio di validazione. | `FactorLibrary`, `run_factor_pipeline`, CLI `fair3 factors`. |
| `fair3.engine.estimates` | Stack di stima media/varianza, fusione Black-Litterman, diagnostica della deriva. | `run_estimate_pipeline`, `estimate_mu_ensemble`. |
| `fair3.engine.allocators` | Generatori di allocazioni, meta-blender e pipeline di ottimizzazione. | `run_optimization_pipeline`, moduli generatori `gen_a.py`–`gen_d_cvar_erc.py`. |
| `fair3.engine.mapping` | Beta fattore-strumento, budget di liquidità, distribuzione intrafattoriale HRP. | `run_mapping_pipeline` e validatori associati. |
| `fair3.engine.execution` | Dimensionamento delle operazioni, modellizzazione costi/tasse e decisioni riepilogative. | `summarise_decision`, primitive di esecuzione. |
| `fair3.engine.reporting` | Rapporti mensili, istantanee di audit, utilità di tracciamento. | `generate_monthly_report`, `run_audit_snapshot`. |
| `fair3.engine.robustness` | Laboratorio di bootstrap, esperimenti di riproduzione, attivatori di ablazione. | `run_robustness_lab`, `RobustnessConfig`. |
| `fair3.engine.utils` | Helper condivisi (I/O, logging, seed, proiezione PSD). | `artifact_path`, `setup_logger`, `generator_from_seed`. |

### Test e garanzia di qualità
- **Imbracatura Pytest:** Il punto di ingresso predefinito è `pytest -q`.Il nuovo `tests/conftest.py` garantisce che la root del repository sia sempre attiva `PYTHONPATH`, stampa il livello di log attivo nell'intestazione del test e abilita i log della pipeline a livello INFO in modo che i test falliti emergano nell'ultimo passaggio eseguito.
- **Test basati sulle proprietà:** le suite basate su ipotesi si trovano in `tests/property/`.Installa la dipendenza opzionale tramite `pip install hypothesis` (già elencata negli extra `pyproject.toml`) per abilitarle localmente.
- **Controlli di verbosità:** Log delle pipeline tramite `fair3.engine.logging.setup_logger`.Migliora la verbosità con `FAIR_LOG_LEVEL=DEBUG` e i log JSON con struttura mirror utilizzando `--json-logs` o `FAIR_JSON_LOGS=1`; la CLI e pytest condividono gli stessi aiutanti di configurazione.
- **Test del fumo mirati:** `tests/unit/test_pipeline_verbosity.py` esercita il fattore, la stima e l'ottimizzazione delle tubazioni con dispositivi leggeri. La suite blocca I/O costosi e continua ad affermare che vengono prodotti artefatti e che le istruzioni di log includono il contesto previsto, rendendo le regressioni più facili da diagnosticare.
- **Istantanee di controllo:** le routine di controllo vengono eseguite automaticamente; nei test vengono patchati per le prestazioni. Durante l'esecuzione end-to-end, verifica che `artifacts/logs/` contenga `seeds.yml`, `checksums.json` e i registri delle modifiche per la verifica della conformità.

Per la riproduzione deterministica, assicurati di esportare `FAIR_LOG_LEVEL` (e facoltativamente `FAIR_JSON_LOGS=1`) prima di richiamare la CLI o i test. Esempio:

```bash
export FAIR_LOG_LEVEL=DEBUG
pytest tests/unit/test_pipeline_verbosity.py -vv
```

## Risoluzione dei problemi (Windows)
- **Strumenti di compilazione:** Installa il carico di lavoro "Sviluppo desktop con C++" (Visual Studio Build Tools) se `cvxpy` richiede la compilazione.
- **Errori SSL:** Aggiorna i certificati Windows o installa `pip install certifi`.Se necessario, impostare `SSL_CERT_FILE` sul pacchetto certificati.
- **Caratteri Matplotlib:** esegui `python -c "import matplotlib.pyplot as plt"` una volta per attivare la creazione della cache dei caratteri. Elimina `%USERPROFILE%\.matplotlib` se danneggiato.
- **Percorsi lunghi:** Abilita il supporto per percorsi lunghi tramite `reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f` (richiede amministratore).

## FAQ
**Perché applicare le covarianze PSD?** Gli ottimizzatori richiedono matrici PSD per evitare varianze negative arbitrabili e garantire soluzioni stabili.

**Perché utilizzare HRP come base?** HRP fornisce allocazioni diversificate con un basso turnovere funge da solido punto di riferimento per i cancelli di accettazione.

**Come vengono semplificate le tasse italiane?** Plusvalenze tassate al 26%, titoli di stato qualificanti proporzionali al 12, 5%, imposta di bollo 0, 2%, perdite monitorate per quattro anni. Consulta un professionista per portafogli reali.

**Come si evita la distorsione look-ahead?** ETL crea pannelli point-in-time con funzionalità ritardate e pieghe di convalida incrociata soggette a embargo.

**Perché così tanti artefatti di audit?** Seeds, istantanee di configurazione e checksum consentono la riproducibilità e il tracciamento di livello normativo.

## Licenza
Questo progetto è rilasciato sotto la licenza Apache 2.0 (vedi `LICENSE`).
