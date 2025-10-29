"""Utility helpers for FAIR-III."""

from fair3.engine.logging import configure_cli_logging, record_metrics, setup_logger

from .io import (
    ARTIFACTS_ROOT,
    artifact_path,
    compute_checksums,
    copy_with_timestamp,
    ensure_dir,
    read_yaml,
    safe_path_segment,
    sha256_file,
    write_json,
    write_yaml,
)
from .psd import project_to_psd
from .rand import (
    DEFAULT_SEED,
    DEFAULT_SEED_PATH,
    DEFAULT_STREAM,
    broadcast_seed,
    generator_from_seed,
    load_seeds,
    save_seeds,
    seed_for_stream,
    spawn_child_rng,
)
from .storage import (
    ASSET_PANEL_SCHEMA,
    ensure_metadata_schema,
    persist_parquet,
    pit_align,
    recon_multi_source,
    to_eur_base,
    total_return,
    upsert_sqlite,
)

__all__ = [
    "ARTIFACTS_ROOT",
    "artifact_path",
    "compute_checksums",
    "copy_with_timestamp",
    "ensure_dir",
    "safe_path_segment",
    "read_yaml",
    "sha256_file",
    "write_json",
    "write_yaml",
    "ASSET_PANEL_SCHEMA",
    "ensure_metadata_schema",
    "persist_parquet",
    "pit_align",
    "recon_multi_source",
    "to_eur_base",
    "total_return",
    "upsert_sqlite",
    "configure_cli_logging",
    "record_metrics",
    "setup_logger",
    "DEFAULT_SEED",
    "DEFAULT_SEED_PATH",
    "DEFAULT_STREAM",
    "broadcast_seed",
    "generator_from_seed",
    "load_seeds",
    "save_seeds",
    "seed_for_stream",
    "spawn_child_rng",
    "project_to_psd",
]
