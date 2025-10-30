# Osservabilità e telemetria

FAIR-III v0.2 centralizza la registrazione e la telemetria di runtime per rendere le prime CLI di Windows
eseguibili con debug senza un'infrastruttura personalizzata.

## Registrazione strutturata

- Utilizza `fair3.engine.logging.setup_logger(name, json_format=False, level=None)` in
  ogni modulo. L'helper legge `FAIR_LOG_LEVEL` (predefinito `INFO`) e allega automaticamente un
  gestore della console.
- Quando `json_format=True` o `FAIR_JSON_LOGS=1`, il logger esegue anche il mirroring dei record
  a `artifacts/logs/fair3.log` come JSON a riga singola contenente
  `timestamp`, `level`, `source`, `message`, `process_time_ms`,
  `bytes_downloaded`, `rows_processed` e `ratelimit_event`.
- CLI esegue l'esposizione`--json-logs/--no-json-logs` e chiama
  `configure_cli_logging()` in modo che tutti i logger `fair3.*` condividano la stessa
  configurazione.

## Flusso di metriche

Chiama `record_metrics(metric_name, value, tags=None)` per aggiungere indicatori numerici
(ad esempio righe importate, iterazioni bootstrap) in
`artifacts/logs/metrics.jsonl`.Ogni riga acquisisce un timestamp UTC, il nome della metrica
, il valore float e tag stringa opzionali. È sicuro richiamare le metriche da
comandi multipli; l'helper garantisce che la directory di controllo esista.

## Barre di avanzamento

I fetcher di acquisizione ora racchiudono i download di simboli con `tqdm`, attivati ​​tramite
`--progress` o `--no-progress` sulla CLI.La barra di avanzamento mostra
`ingest:<SOURCE>` con gli aggiornamenti per simbolo e scompare automaticamente quando
disabilitato (impostazione predefinita).

## Test Harness Integration

I dispositivi Pytest si basano sugli stessi helper: il dispositivo autouse in
`tests/conftest.py` imposta `FAIR_LOG_LEVEL=INFO` in modo che i test unitari ereditino una coerenza
verbosità. I singoli test possono attivare la registrazione JSON impostando
`FAIR_JSON_LOGS=1` o chiamando `configure_cli_logging(True)`.

## Risoluzione dei problemi

| Sintomo | Probabile causa | Correzione |
| --- | --- | --- |
| File di registro JSON mancante | `--json-logs` non superato e `FAIR_JSON_LOGS` non impostato | Esegui con `fair3 ... --json-logs` o esporta `FAIR_JSON_LOGS=1`. |
| Barra di avanzamento non visibile | In esecuzione in CI o `--no-progress` | Passa `--progress` esplicitamente; il flag predefinito è `False`. |
| Righe di registro duplicate | Logger riconfigurato senza cancellare i gestori | Affidarsi al cablaggio `setup_logger` (idempotente) anziché al comando manuale. |

Tutti i percorsi e i nomi dei file sono relativi alla radice del progetto per facilitare la compatibilità e la riproducibilità di Windows
.
