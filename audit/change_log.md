# FAIR-III v0.2 Change Log

## 2025-03-15 — Data persistence alignment

- Added the canonical `data/clean/asset_panel.parquet` dataset with UTC
  timestamps, PIT flagging, per-row checksum and licensing metadata.
- Introduced the shared storage utilities (`persist_parquet`,
  `upsert_sqlite`, `recon_multi_source`, `total_return`, `pit_align`,
  `to_eur_base`) and created the FAIR metadata schema for SQLite ingest logs.
- Updated ingest fetchers to log audit information into the metadata SQLite
  database (`ingest_log`, `instrument`, `source_map`) alongside raw CSV
  persistence.
- Refreshed CLI/tests/docs to reflect the new panel artefact and checksum
  reporting while maintaining backwards compatibility fallbacks.
