# Ingest Module

## Scopo
Il sottosistema di ingest raccoglie dati grezzi da fonti pubbliche (ECB, FRED, Bank of England, Stooq) e li salva sotto `data/raw/<source>/` in formato CSV, garantendo retry/backoff e tracciabilità della licenza.

## API pubbliche
- `BaseCSVFetcher.fetch(symbols=None, start=None, as_of=None)` scarica uno o più simboli restituendo un `IngestArtifact` con `data`, `path` e metadati (licenza, URL richiesti, timestamp).
- `available_sources()` elenca i codici sorgente supportati.
- `create_fetcher(source, **kwargs)` restituisce l'istanza di fetcher pronta all'uso.
- `run_ingest(source, symbols=None, start=None, raw_root=None, as_of=None)` è l'entry point usato dal CLI.

Tutti i fetcher accettano `raw_root` opzionale per redirigere l'output (utile nei test) e loggano automaticamente licenza e URL tramite `fair3.engine.logging.setup_logger`.

## Utilizzo CLI
```bash
fair3 ingest --source ecb --symbols USD GBP --from 2020-01-01
```
- `--source`: uno tra `ecb`, `fred`, `boe`, `stooq`.
- `--symbols`: lista opzionale di simboli specifici della sorgente (default codificati per ogni fetcher).
- `--from`: data minima (ISO `YYYY-MM-DD`) per filtrare le osservazioni.

Il comando stampa un riepilogo con numero di righe e percorso del CSV prodotto. I log ruotati sono salvati in `artifacts/audit/fair3_ingest_<source>.log`.

## Esempi Python
```python
from fair3.engine.ingest import run_ingest

result = run_ingest("fred", symbols=["DGS10"], start="2022-01-01")
print(result.path)
print(result.data.head())
```

## Flag `--trace`
Il tracciamento fine-grained verrà agganciato nei prossimi PR tramite l'opzione `--trace` del CLI. Al momento i fetcher espongono messaggi INFO con URL e licenza associati a ogni simbolo.

## Errori comuni
- **`ValueError: At least one symbol must be provided`**: nessun simbolo di default e lista vuota passata.
- **`requests.HTTPError`**: risposta non 200 dopo i retry previsti; controllare connettività o permessi della fonte dati.
- **`ValueError: Expected columns ...`**: il payload CSV non contiene le colonne attese, spesso dovuto a simbolo errato.

## Log e audit
Ogni esecuzione registra i dettagli in `IngestArtifact.metadata` (licenza, URL, timestamp, start-date) e crea file CSV datati (`<source>_YYYYMMDDTHHMMSSZ.csv`). Copiare questi metadati in `artifacts/audit/` è responsabilità del modulo `reporting.audit` introdotto nel PR precedente.
