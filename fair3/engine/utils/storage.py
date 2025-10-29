"""Persistence helpers for FAIR-III storage requirements.

This module centralises the logic required by the FAIR-III v0.2
specification for persisting datasets to Parquet with an explicit
``pyarrow`` schema and for recording ingest metadata into SQLite. The
functions exposed here are intentionally composable so that CLI commands
and library callers can share the same deterministic storage layer.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pyarrow import types as pa_types

from fair3.engine.utils.io import ensure_dir, sha256_file

__all__ = [
    "ASSET_PANEL_SCHEMA",
    "FAIR_METADATA_SCHEMA",
    "ensure_metadata_schema",
    "persist_parquet",
    "pit_align",
    "recon_multi_source",
    "to_eur_base",
    "total_return",
    "upsert_sqlite",
]


ASSET_PANEL_SCHEMA = pa.schema(
    [
        pa.field("date", pa.timestamp("ns", tz="UTC")),
        pa.field("symbol", pa.string()),
        pa.field("field", pa.string()),
        pa.field("value", pa.float64()),
        pa.field("currency", pa.string()),
        pa.field("source", pa.string()),
        pa.field("license", pa.string()),
        pa.field("tz", pa.string()),
        pa.field("quality_flag", pa.string()),
        pa.field("revision_tag", pa.string()),
        pa.field("checksum", pa.string()),
        pa.field("pit_flag", pa.int8()),
    ]
)
"""Schema standardizzato per i pannelli asset-level salvati in Parquet."""


FAIR_METADATA_SCHEMA: Mapping[str, str] = {
    "instrument": """
        CREATE TABLE IF NOT EXISTS instrument (
            id TEXT PRIMARY KEY,
            isin TEXT,
            figi TEXT,
            mic TEXT,
            symbol TEXT,
            asset_class TEXT,
            currency TEXT,
            lot REAL,
            adv_hint REAL,
            fee_hint REAL,
            bidask_hint REAL,
            provider_pref TEXT,
            ucits_flag INTEGER,
            govies_share_hint REAL,
            ter_hint REAL,
            kid_url TEXT
        );
    """,
    "source_map": """
        CREATE TABLE IF NOT EXISTS source_map (
            instrument_id TEXT,
            preferred_source TEXT,
            fallback_source TEXT,
            url TEXT,
            license TEXT,
            rate_limit_note TEXT,
            last_success DATETIME,
            etag TEXT,
            last_modified DATETIME,
            PRIMARY KEY (instrument_id, preferred_source)
        );
    """,
    "factor_index": """
        CREATE TABLE IF NOT EXISTS factor_index (
            factor_id TEXT PRIMARY KEY,
            name TEXT,
            category TEXT,
            long_sign INTEGER,
            proxy_universe TEXT,
            notes TEXT
        );
    """,
    "ingest_log": """
        CREATE TABLE IF NOT EXISTS ingest_log (
            ts DATETIME,
            source TEXT,
            endpoint TEXT,
            symbol TEXT,
            status TEXT,
            http_code INTEGER,
            bytes INTEGER,
            rows INTEGER,
            duration_s REAL,
            retries INTEGER,
            warning TEXT,
            checksum_sha256 TEXT,
            PRIMARY KEY (ts, source, symbol, endpoint)
        );
    """,
}
"""Mappa tabella SQL → statement DDL per la base dati FAIR."""


def ensure_metadata_schema(conn: sqlite3.Connection) -> None:
    """Create metadata tables if they are missing.

    Args:
      conn: Connessione SQLite aperta sulla base dati FAIR.

    Il metodo è idempotente ed esegue le istruzioni DDL definite in
    :data:`FAIR_METADATA_SCHEMA`.  Nessuna tabella viene ricreata se già
    presente, così da preservare i dati storici.
    """

    cursor = conn.cursor()
    for ddl in FAIR_METADATA_SCHEMA.values():
        cursor.executescript(ddl)
    conn.commit()


def persist_parquet(df: pd.DataFrame, path: Path | str, schema: pa.Schema) -> tuple[Path, str]:
    """Persist a DataFrame to Parquet using the provided schema.

    Args:
      df: Frame già normalizzato secondo lo schema FAIR.
      path: Destinazione del file Parquet.
      schema: Schema ``pyarrow`` da utilizzare durante la serializzazione.

    Returns:
      Coppia ``(path, checksum)`` con il percorso assoluto del file scritto e
      l'hash SHA-256 calcolato sul payload, utile per audit trail.

    Raises:
      ValueError: Se le colonne richieste dallo schema non sono presenti nel
        ``DataFrame``.
    """

    required_columns = {field.name for field in schema}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for Parquet persistence: {sorted(missing)}")

    target_path = Path(path)
    ensure_dir(target_path.parent)
    sanitized = df.copy()
    for field in schema:
        column = field.name
        if column not in sanitized.columns:
            continue
        if pa_types.is_float64(field.type):
            sanitized[column] = sanitized[column].astype(float)
        elif pa_types.is_int8(field.type):
            sanitized[column] = sanitized[column].astype("int8")
        elif pa_types.is_timestamp(field.type):
            sanitized[column] = pd.to_datetime(sanitized[column], utc=True)
    table = pa.Table.from_pandas(sanitized, schema=schema, preserve_index=False)
    pq.write_table(table, target_path, compression="snappy")
    checksum = sha256_file(target_path)
    return target_path, checksum


def upsert_sqlite(
    conn: sqlite3.Connection,
    table: str,
    df: pd.DataFrame,
    keys: Iterable[str],
) -> int:
    """Perform an UPSERT into ``table`` using ``keys`` as the conflict target.

    Args:
      conn: Connessione SQLite aperta.
      table: Nome della tabella su cui effettuare l'inserimento.
      df: Dati da inserire; le colonne devono corrispondere alla tabella.
      keys: Colonne che definiscono l'univocità e vengono usate per l'``ON
        CONFLICT``.

    Returns:
      Numero di righe interessate dall'operazione.

    Raises:
      ValueError: Se il ``DataFrame`` è vuoto oppure se le colonne chiave non
        sono presenti.
    """

    if df.empty:
        return 0
    key_list = list(keys)
    missing_keys = set(key_list) - set(df.columns)
    if missing_keys:
        raise ValueError(f"Missing key columns for upsert: {sorted(missing_keys)}")

    columns = list(df.columns)
    placeholders = ", ".join(["?"] * len(columns))
    assignments = ", ".join(f"{col}=excluded.{col}" for col in columns if col not in key_list)
    conflict_clause = ", ".join(key_list)
    sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    if assignments:
        sql += f" ON CONFLICT({conflict_clause}) DO UPDATE SET {assignments}"
    else:
        sql += f" ON CONFLICT({conflict_clause}) DO NOTHING"

    values = [tuple(row) for row in df.itertuples(index=False, name=None)]
    cursor = conn.executemany(sql, values)
    conn.commit()
    return cursor.rowcount


def recon_multi_source(
    primary: pd.Series,
    secondary: pd.Series,
    tol_abs: float,
    tol_rel: float,
) -> pd.DataFrame:
    """Cross-check two series and flag mismatches beyond tolerances.

    Args:
      primary: Serie principale (es. fonte prioritaria) indicizzata per data.
      secondary: Serie di confronto allineata temporalmente alla primaria.
      tol_abs: Soglia assoluta massima ammessa.
      tol_rel: Soglia relativa massima ammessa (in termini di frazione).

    Returns:
      DataFrame con colonne ``primary``, ``secondary``, ``abs_diff``,
      ``rel_diff`` e ``mismatch`` (boolean) più gli indici originali
      ripristinati come colonne.
    """

    aligned = pd.concat([primary.rename("primary"), secondary.rename("secondary")], axis=1)
    aligned = aligned.sort_index()
    aligned["abs_diff"] = (aligned["primary"] - aligned["secondary"]).abs()
    denom = aligned["secondary"].replace(0.0, np.nan).abs()
    aligned["rel_diff"] = aligned["abs_diff"] / denom
    aligned["rel_diff"] = aligned["rel_diff"].fillna(0.0)
    aligned["mismatch"] = (aligned["abs_diff"] > tol_abs) & (aligned["rel_diff"] > tol_rel)
    aligned = aligned.reset_index()
    return aligned


def to_eur_base(df: pd.DataFrame, fx_panel: pd.DataFrame) -> pd.DataFrame:
    """Convert a price panel to EUR using ECB FX rates at 16:00 CET.

    Args:
      df: Frame con colonne ``date``, ``value`` e ``currency``.
      fx_panel: Serie FX già espressa in EUR e indicizzata da ``date``.

    Returns:
      DataFrame convertito in EUR con colonna ``currency`` valorizzata a ``EUR``.
    """

    if df.empty:
        return df
    required = {"date", "value", "currency"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns for FX conversion: {sorted(missing)}")

    work = df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work.sort_values("date")
    fx_rates = fx_panel.reindex(work["date"]).ffill()
    fx_rates = fx_rates.fillna(method="bfill").fillna(1.0)
    work["value"] = work["value"] * fx_rates.to_numpy()
    work["currency_original"] = work["currency"]
    work["currency"] = "EUR"
    return work


def total_return(price_df: pd.DataFrame, distributions: pd.DataFrame | None = None) -> pd.DataFrame:
    """Compute total-return series reinvesting cash flows.

    Args:
      price_df: Serie di prezzi già ordinata per data con colonne ``date``,
        ``symbol`` e ``price``.
      distributions: Eventuali dividendi/cedole con colonne ``date``, ``symbol``
        e ``amount``; opzionale.

    Returns:
      Frame con colonne ``date``, ``symbol`` e ``total_return`` normalizzato a 1
      sul primo punto disponibile.
    """

    if price_df.empty:
        return pd.DataFrame(columns=["date", "symbol", "total_return"])

    work = price_df.copy()
    work["date"] = pd.to_datetime(work["date"])
    work = work.sort_values(["symbol", "date"])  # type: ignore[list-item]
    work["price"] = work["price"].astype(float)

    if distributions is not None and not distributions.empty:
        distributions = distributions.copy()
        distributions["date"] = pd.to_datetime(distributions["date"])
        distributions = distributions.sort_values(["symbol", "date"])
        work = work.merge(distributions, on=["symbol", "date"], how="left")
        work["amount"] = work["amount"].fillna(0.0)
    else:
        work["amount"] = 0.0

    totals: list[pd.DataFrame] = []
    for symbol, sub in work.groupby("symbol", sort=False):
        prices = sub["price"].to_numpy(dtype=float)
        flows = sub["amount"].to_numpy(dtype=float)
        total = np.empty_like(prices)
        total[0] = 1.0
        for idx in range(1, len(prices)):
            if prices[idx - 1] == 0:
                growth = 1.0
            else:
                growth = (prices[idx] + flows[idx]) / prices[idx - 1]
            total[idx] = total[idx - 1] * growth
        totals.append(
            pd.DataFrame(
                {
                    "date": sub["date"].to_numpy(),
                    "symbol": symbol,
                    "total_return": total,
                }
            )
        )
    return pd.concat(totals, ignore_index=True)


def pit_align(df: pd.DataFrame, lag_days: int) -> pd.DataFrame:
    """Apply a point-in-time lag to slow-moving features.

    Args:
      df: Frame con colonna ``date`` e qualsiasi altra informazione numerica.
      lag_days: Numero di giorni di lag da applicare.

    Returns:
      Copia del DataFrame con ``date`` traslata indietro di ``lag_days``.
    """

    if df.empty:
        return df
    work = df.copy()
    work["date"] = pd.to_datetime(work["date"]) - pd.Timedelta(days=lag_days)
    return work
