"""Utility di I/O con commenti e docstring localizzati in italiano.

Il modulo fornisce helper riutilizzabili per gestire directory di artefatti,
sanitizzare nomi di file e serializzare strutture dati in formato YAML/JSON.
Le funzioni privilegiano robustezza e trasparenza per supportare il debug.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import yaml

# Cartella principale dove la pipeline salva gli artefatti intermedi e finali.
ARTIFACTS_ROOT = Path("artifacts")

__all__ = [
    "ARTIFACTS_ROOT",
    "ensure_dir",
    "safe_path_segment",
    "artifact_path",
    "read_yaml",
    "write_yaml",
    "sha256_file",
    "compute_checksums",
    "copy_with_timestamp",
    "write_json",
]


# Espressione regolare che intercetta caratteri vietati nei nomi di file.
INVALID_FS_CHARS = r'[<>:"/\\|?*\x00-\x1F]'


def ensure_dir(path: Path | str) -> Path:
    """Garantisce l'esistenza del percorso e lo restituisce come :class:`Path`."""

    # Creiamo la directory con ``parents=True`` per evitare race condition
    # qualora venisse invocata in parallelo da più processi.
    path_obj = Path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def safe_path_segment(name: str) -> str:
    """Restituisce ``name`` ripulito dai caratteri non ammessi dal filesystem."""

    # Sostituiamo i caratteri proibiti con ``-`` e rimuoviamo spazi finali per
    # produrre un segmento conforme indipendentemente dal sistema operativo.
    safe = re.sub(INVALID_FS_CHARS, "-", str(name))
    return safe.rstrip(" .")


def artifact_path(
    *parts: str,
    create: bool = True,
    root: Path | str | None = None,
) -> Path:
    """Costruisce un percorso all'interno della directory degli artefatti."""

    base = Path(root) if root is not None else ARTIFACTS_ROOT
    target = base.joinpath(*parts)
    # L'opzione ``create`` permette di disabilitare la creazione preventiva per
    # test che vogliono verificare il comportamento in assenza della cartella.
    if create:
        target.parent.mkdir(parents=True, exist_ok=True)
    return target


def read_yaml(path: Path | str) -> object:
    """Legge un file YAML e restituisce l'oggetto Python corrispondente."""

    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(data: object, path: Path | str) -> Path:
    """Scrive ``data`` nel percorso indicato in formato YAML leggibile."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        # ``sort_keys`` garantisce diff deterministici durante i test.
        yaml.safe_dump(data, handle, sort_keys=True)
    return target


def sha256_file(path: Path | str, *, chunk_size: int = 65_536) -> str:
    """Calcola l'hash SHA-256 del file in modo incrementale."""

    import hashlib

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        # Usiamo un iteratore esplicito per gestire file grandi senza caricarli.
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_checksums(paths: Iterable[Path | str]) -> dict[str, str]:
    """Restituisce una mappa ``percorso -> checksum`` per i file esistenti."""

    result: dict[str, str] = {}
    for file_path in paths:
        path = Path(file_path)
        if not path.exists():
            # I file mancanti vengono ignorati così da poter passare liste eterogenee.
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
    """Copia ``src`` in ``dest_dir`` aggiungendo un timestamp UTC al nome file."""

    src_path = Path(src)
    if not src_path.exists():
        # Solleviamo esplicitamente l'errore per aiutare il chiamante nel debug.
        raise FileNotFoundError(src_path)

    ts = timestamp or datetime.now(UTC)
    label = prefix or src_path.stem
    dest_directory = ensure_dir(dest_dir)
    target_name = f"{label}_{ts.strftime('%Y%m%dT%H%M%SZ')}{src_path.suffix}"
    target_path = dest_directory / target_name
    shutil.copy2(src_path, target_path)
    return target_path


def write_json(data: object, path: Path | str, *, indent: int = 2) -> Path:
    """Serializza ``data`` in JSON garantendo un'ultima riga con newline."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=indent, sort_keys=True)
        # Aggiungiamo ``\n`` finale per conformità con gli standard interni.
        handle.write("\n")
    return target
