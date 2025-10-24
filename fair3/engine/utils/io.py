from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import yaml

ARTIFACTS_ROOT = Path("artifacts")

__all__ = [
    "ARTIFACTS_ROOT",
    "ensure_dir",
    "artifact_path",
    "read_yaml",
    "write_yaml",
    "sha256_file",
    "compute_checksums",
    "copy_with_timestamp",
    "write_json",
]


def ensure_dir(path: Path | str) -> Path:
    """Ensure ``path`` exists and return it as a :class:`Path`."""

    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def artifact_path(
    *parts: str,
    create: bool = True,
    root: Path | str | None = None,
) -> Path:
    """Return a path under the artifacts directory.

    Parameters
    ----------
    parts:
        Path components below the root.
    create:
        When ``True``, ensure the parent directory exists.
    root:
        Custom root directory. Defaults to ``artifacts``.
    """

    base = Path(root) if root is not None else ARTIFACTS_ROOT
    target = base.joinpath(*parts)
    if create:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


def read_yaml(path: Path | str) -> object:
    """Read a YAML file returning the parsed object."""

    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(data: object, path: Path | str) -> Path:
    """Write ``data`` to ``path`` in YAML format."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=True)
    return target


def sha256_file(path: Path | str, *, chunk_size: int = 65_536) -> str:
    """Compute the SHA-256 checksum for ``path``."""

    import hashlib

    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_checksums(paths: Iterable[Path | str]) -> dict[str, str]:
    """Return a mapping of file name to checksum for the given paths."""

    result: dict[str, str] = {}
    for file_path in paths:
        path = Path(file_path)
        if not path.exists():
            continue
        result[str(path)] = sha256_file(path)
    return result


def copy_with_timestamp(
    src: Path | str,
    dest_dir: Path | str,
    *,
    prefix: str | None = None,
    timestamp: datetime | None = None,
) -> Path:
    """Copy ``src`` into ``dest_dir`` with a UTC timestamp in the filename."""

    src_path = Path(src)
    if not src_path.exists():
        raise FileNotFoundError(src_path)

    ts = timestamp or datetime.now(UTC)
    label = prefix or src_path.stem
    dest_directory = ensure_dir(dest_dir)
    target_name = f"{label}_{ts.strftime('%Y%m%dT%H%M%SZ')}{src_path.suffix}"
    target_path = dest_directory / target_name
    shutil.copy2(src_path, target_path)
    return target_path


def write_json(data: object, path: Path | str, *, indent: int = 2) -> Path:
    """Serialize ``data`` as JSON to ``path``."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=indent, sort_keys=True)
        handle.write("\n")
    return target
