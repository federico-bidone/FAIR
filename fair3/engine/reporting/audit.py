from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from fair3.engine.utils.io import (
    compute_checksums,
    copy_with_timestamp,
    ensure_dir,
    write_json,
    write_yaml,
)
from fair3.engine.utils.rand import DEFAULT_SEED_PATH, load_seeds

__all__ = [
    "ensure_audit_dir",
    "copy_seed_snapshot",
    "snapshot_configs",
    "record_checksums",
    "append_change_log",
    "run_audit_snapshot",
]


def ensure_audit_dir(audit_dir: Path | str | None = None) -> Path:
    """Ensure and return the audit directory."""

    return ensure_dir(audit_dir or (Path("artifacts") / "audit"))


def copy_seed_snapshot(
    seed_path: Path | str = DEFAULT_SEED_PATH,
    *,
    audit_dir: Path | str | None = None,
    timestamp: datetime | None = None,
) -> Path:
    """Copy the current seed file into the audit directory with timestamp."""

    src = Path(seed_path)
    if not src.exists():
        seeds = load_seeds(seed_path)
        ensure_dir(Path(seed_path).parent)
        write_yaml({"seeds": seeds}, seed_path)
    audit_path = ensure_audit_dir(audit_dir)
    ts = timestamp or datetime.now(UTC)
    history_dir = audit_path / "seeds_history"
    stamped = copy_with_timestamp(src, history_dir, prefix="seeds", timestamp=ts)
    dest = audit_path / "seeds.yml"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return stamped


def snapshot_configs(
    config_paths: Iterable[Path | str],
    *,
    audit_dir: Path | str | None = None,
    timestamp: datetime | None = None,
) -> list[Path]:
    """Copy provided configuration files into the audit directory."""

    audit_path = ensure_audit_dir(audit_dir)
    ts = timestamp or datetime.now(UTC)
    snapshots: list[Path] = []
    configs_dir = audit_path / "configs"
    for cfg in config_paths:
        cfg_path = Path(cfg)
        if not cfg_path.exists():
            continue
        prefix = cfg_path.stem
        options = {"prefix": prefix, "timestamp": ts}
        snapshot = copy_with_timestamp(cfg_path, configs_dir, **options)
        snapshots.append(snapshot)
    return snapshots


def record_checksums(
    targets: Mapping[str, str] | Iterable[Path | str],
    *,
    audit_dir: Path | str | None = None,
    timestamp: datetime | None = None,
) -> Path:
    """Persist checksums for the provided targets."""

    audit_path = ensure_audit_dir(audit_dir)
    ts = (timestamp or datetime.now(UTC)).isoformat()
    if isinstance(targets, Mapping):
        checksum_map = {str(k): str(v) for k, v in targets.items()}
    else:
        checksum_map = compute_checksums(targets)
    payload = {"timestamp": ts, "files": checksum_map}
    path = audit_path / "checksums.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, list):
            existing.append(payload)
        else:
            existing = [existing, payload]
    else:
        existing = [payload]
    write_json(existing, path)
    return path


def append_change_log(
    message: str,
    *,
    audit_dir: Path | str | None = None,
    timestamp: datetime | None = None,
) -> Path:
    """Append ``message`` to the audit change log."""

    audit_path = ensure_audit_dir(audit_dir)
    ts = timestamp or datetime.now(UTC)
    stamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"- {stamp} {message.strip()}\n"
    path = audit_path / "change_log.md"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
    return path


def run_audit_snapshot(
    *,
    seed_path: Path | str = DEFAULT_SEED_PATH,
    config_paths: Sequence[Path | str] = (),
    checksums: Mapping[str, str] | None = None,
    note: str | None = None,
    audit_dir: Path | str | None = None,
    timestamp: datetime | None = None,
) -> dict[str, Path]:
    """Execute the standard audit routine and return generated paths."""

    ts = timestamp or datetime.now(UTC)
    audit_path = ensure_audit_dir(audit_dir)
    generated: dict[str, Path] = {}

    seed_snapshot = copy_seed_snapshot(seed_path, audit_dir=audit_path, timestamp=ts)
    generated["seed_snapshot"] = seed_snapshot
    config_snaps = snapshot_configs(config_paths, audit_dir=audit_path, timestamp=ts)
    if config_snaps:
        generated["config_snapshots"] = config_snaps
    checksum_path = record_checksums(
        checksums if checksums is not None else config_paths,
        audit_dir=audit_path,
        timestamp=ts,
    )
    generated["checksums"] = checksum_path

    summary_parts = []
    if note:
        summary_parts.append(note)
    if config_paths:
        existing = [Path(cfg).name for cfg in config_paths if Path(cfg).exists()]
        if existing:
            summary_parts.append("Configs: " + ", ".join(existing))
    if summary_parts:
        generated["changelog"] = append_change_log(
            "; ".join(summary_parts), audit_dir=audit_path, timestamp=ts
        )

    return generated
