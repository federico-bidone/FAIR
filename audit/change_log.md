# Registro modifiche FAIR-III v0.2

## 15-03-2025 — Allineamento della persistenza dei dati

- Aggiunto il set di dati canonico `data/clean/asset_panel.parquet` con UTC
  timestamp, contrassegno PIT, checksum per riga e metadati di licenza.
- Introdotte le utilità di archiviazione condivisa(`persist_parquet`,
  `upsert_sqlite`, `recon_multi_source`, `total_return`, `pit_align`,
  `to_eur_base`) e ha creato lo schema di metadati FAIR per i log di acquisizione SQLite.
- Recuper di acquisizione aggiornati per registrare le informazioni di controllo nei metadati SQLite
  database (`ingest_log`, `instrument`, `source_map`) insieme al CSV non elaborato
  persistenza.
- CLI/test/documenti aggiornati per riflettere il nuovo artefatto del pannello e checksum
  report mantenendo i fallback di compatibilità con le versioni precedenti.
