# ETL Module

## Scopo
Il modulo ETL costruisce un pannello point-in-time (PIT) di prezzi totali, rendimenti e feature laggate a partire dagli snapshot raw generati dall'ingest. L'obiettivo è ottenere serie pulite e riproducibili per l'intera pipeline (`factors`, `estimate`, `optimize`, ...), rispettando i vincoli anti-look-ahead e mantenendo tracciabilità completa (QA log, FX applicato, seed).

## API pubbliche
- `build_tr_panel(**kwargs)` / `TRPanelBuilder`: orchestration principale. Scrive `asset_panel.parquet` in `data/clean/` rispettando lo schema FAIR e `audit/qa_data_log.csv` per la QA.
- `TradingCalendar`, `build_calendar`, `reindex_frame`: utility per calendarizzare e allineare serie multi-sorgente.
- `apply_hampel`, `clean_price_history`, `winsorize_series`, `prepare_estimation_copy`: funzioni di pulizia e preparazione per le fasi di stima.
- `FXFrame`, `load_fx_rates`, `convert_to_base`: normalizzazione valutaria verso la base (`EUR` di default).
- `QAReport`, `write_qa_log`: costruzione e persistenza del log QA.

Le API restituiscono `pandas.DataFrame` con MultiIndex `(date, symbol)` e colonne documentate nei rispettivi moduli. Tutte le funzioni accettano argomenti espliciti per percorsi di input/output così da agevolare i test.

## Esempi d'uso
```python
from fair3.engine.etl import TRPanelBuilder

builder = TRPanelBuilder(raw_root="data/raw", clean_root="data/clean", audit_root="audit", base_currency="EUR")
artifacts = builder.build(seed=0, trace=True)
print(artifacts.panel_path)
```

CLI equivalente:
```bash
fair3 etl --rebuild --base-currency EUR
```
Flag aggiuntivi per test/local-dev (nascosti nel `--help`): `--raw-root`, `--clean-root`, `--audit-root`, `--seed`, `--trace`.

## Artefatti generati
- `data/clean/asset_panel.parquet`: pannello long con campi `field`, `value`, `currency`, `source`, `license`, `tz`, `quality_flag`, `revision_tag`, `checksum`, `pit_flag`.
- `audit/qa_data_log.csv`: QA per simbolo (copertura, nulls, outliers, currency applied).

## Tracing e logging
Abilitando `--trace` si ottiene un log sintetico su stdout (numero di file raw trovati); i log strutturati sono salvati via `write_qa_log`. Ulteriori step di tracing saranno agganciati alla rotazione log centralizzata (`fair3.engine.logging`).

## Errori comuni
- **Nessun raw trovato**: eseguire prima `fair3 ingest --source ...` per popolari `data/raw/`.
- **Colonne mancanti**: i CSV raw devono contenere `date`, `value`, `symbol`; eventuali colonne `currency` vengono forward-fillate.
- **FX non disponibile**: se mancano serie FX coerenti, l'ETL assume identità (`fx_rate=1.0`) e registra la currency originale.
- **Dipendenze parquet**: assicurarsi che `pyarrow` sia installato (incluso nelle dipendenze core del progetto).

## Flag `--trace`
Il flag `--trace` stampa su stdout il numero di file raw processati ed è utile in CI/local debugging; non modifica la logica di calcolo.

## Dove trovare i log
- `audit/qa_data_log.csv`: QA tabellare appendibile (ordinato per `symbol`, `source`).
- Log futuri (rolling file) saranno gestiti da `fair3.engine.logging` e collegati in questa sezione in milestone dedicate.
