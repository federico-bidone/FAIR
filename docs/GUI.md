# FAIR-III GUI (PySide6)

> Strumento informativo/didattico; non costituisce consulenza finanziaria o raccomandazione.

La GUI opzionale di FAIR-III fornisce un pannello di controllo moderno per orchestrare
ingest, pipeline e reportistica senza abbandonare la semantica deterministica della
CLI. Ogni azione lanciata dalla finestra utilizza gli stessi moduli Python impiegati
nei comandi `fair3`, così i workflow restano riproducibili anche in ambienti headless.

## Installazione rapida

```bash
pip install .[gui]
# dipendenze facoltative per Yahoo Finance
pip install .[data]
```

L'extra `gui` installa PySide6 e `keyring`, necessario per
persistire in modo sicuro le chiavi API. L'extra `data` aggiunge `yfinance`,
richiesto per l'ingest Yahoo. Se PySide6 non è presente, il launcher
mostra un messaggio con il comando da eseguire e termina senza errori, lasciando
la CLI completamente operativa.

## Avvio

```bash
fair3 gui            # riutilizza le stesse directory configurate per la CLI
fair3-gui            # entry point diretto installato da pyproject.toml
```

L'opzione `--dry-run` stampa la configurazione derivata senza aprire la finestra.
Gli override disponibili coincidono con quelli della CLI (`--raw-root`,
`--clean-root`, `--universe-root`, `--report-root`, `--artifacts-root`, ...).

## Struttura della finestra

La GUI è composta da un `QTabWidget` con cinque pannelli coordinati da
`fair3.engine.gui.mainwindow.FairMainWindow`:

- **Broker** – elenca i broker registrati, permette la selezione/deselezione
  rapida e avvia la pipeline Universe utilizzando OpenFIGI quando la chiave è
  presente nel keyring.
- **Data provider** – consente ingest puntuali scegliendo la sorgente registrata,
  simboli opzionali e la data minima di download, con conversione QDate
  compatibile PySide6 (`toPython` + fallback). Se si sceglie *yahoo* senza aver
  installato `yfinance`, il pannello suggerisce `pip install .[data]`.
- **Pipeline** – espone due modalità: una automatica completa (Universe → ingest
  multi-provider → ETL → fattori → stime → report) e una manuale
  personalizzabile. Quest'ultima permette di selezionare quali step eseguire, i
  broker target e, per l'ingest, il provider e la lista di simboli. Le esecuzioni
  avvengono in thread di lavoro (`QThreadPool`) per evitare blocchi dell'interfaccia.
- **API key** – genera dinamicamente un campo per ogni sorgente che richiede
  credenziali, salva/testa/cancella i token nel keyring di sistema (mostrando
  solo `***ABCD` per indicare i valori salvati) e permette un test rapido della
  presenza delle chiavi.
- **Report** – mostra le cartelle generate in `artifacts/reports/`, elenca i
  principali artefatti (PDF, CSV, JSON, PNG) e visualizza un riepilogo delle
  metriche (`summary.json`). Il pulsante *Apri artefatto* apre il file selezionato
  nel visualizzatore di sistema.

Sotto alle schede è presente una console (`QPlainTextEdit`) che riceve gli stessi
log testuali della CLI e mantiene fino a 2.000 righe recenti; tutti i log JSON
vengono inoltre salvati in `artifacts/logs/fair3.log`.

## Flusso automatico

Il pulsante *Avvia orchestrazione completa* della scheda Pipeline esegue i
seguenti step, registrando eventuali errori senza interrompere l'interfaccia:

1. Costruisce l'universo investibile dei broker selezionati.
2. Deduce i provider preferiti dal file `provider_selection.parquet` e avvia
   l'ingest (con fallback su Alpha Vantage FX, Tiingo e FRED in assenza di dati).
3. Prova a ricostruire il pannello ETL e a generare fattori/stime utilizzando i
   parametri di default di FAIR-III.
4. Se richiesto, crea una cartella timestampata in `artifacts/reports/` e vi
   scrive un report sintetico tramite `generate_monthly_report` (utile come
   placeholder fino alla disponibilità di dati reali) indicando il percorso del
   PDF direttamente nel pannello Report.

## Gestione delle credenziali

Il pannello **API key** interroga `fair3.engine.ingest.registry.credential_fields`
per determinare quali provider richiedono autenticazione. Ogni valore viene
memorizzato tramite `fair3.engine.infra.secrets.save_api_keys` e reso disponibile
nei processi attivi con `apply_api_keys`, evitando file YAML locali. Per gli
ambienti non interattivi è possibile popolare il keyring con comandi come
`keyring set fair3:alphavantage_api_key default`.

## Risoluzione dei problemi

- **PySide6 mancante** – assicurarsi di aver installato `pip install .[gui]`.
- **yfinance mancante** – installare l'extra `pip install .[data]` prima di
  avviare ingest Yahoo.
- **Esecuzioni lente** – la maggior parte dei task gira su `QThreadPool`, ma
  ingest intensivi potrebbero richiedere tempo: consultare la console in basso
  per lo stato dettagliato.
- **Chiavi assenti** – utilizzare il pulsante *Test* accanto a ogni campo per
  verificare se la credenziale è presente nel keyring.
- **Report vuoti** – la pipeline automatica genera report sintetici quando i
  dati reali non sono disponibili; passare al workflow CLI completo per ottenere
  artefatti basati su serie reali.

La GUI rimane un'estensione opzionale: tutte le funzionalità principali continuano
ad essere accessibili e automatizzabili via CLI o orchestratori esterni.
