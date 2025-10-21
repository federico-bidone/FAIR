from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

__all__ = ["setup_logger", "get_logger", "default_log_dir"]


def default_log_dir() -> Path:
    """Return the default audit log directory, ensuring it exists."""
    path = Path("artifacts") / "audit"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _as_level(level: int | str) -> int:
    if isinstance(level, str):
        mapping = logging.getLevelNamesMapping()
        return int(mapping.get(level.upper(), logging.INFO))
    return int(level)


def _file_handler(
    path: Path,
    level: int,
    max_bytes: int,
    backup_count: int,
) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.setLevel(level)
    return handler


def setup_logger(
    name: str,
    *,
    level: int | str = logging.INFO,
    log_dir: Path | str | None = None,
    max_bytes: int = 1_048_576,
    backup_count: int = 5,
    console: bool = False,
    propagate: bool = False,
) -> logging.Logger:
    """Configure and return a rotating-file logger.

    Parameters
    ----------
    name:
        Logger name. Will also be used to derive the log file name.
    level:
        Logging level (numeric or string).
    log_dir:
        Optional directory for log files. Defaults to ``artifacts/audit``.
    max_bytes:
        Maximum size of a single log file before rotation.
    backup_count:
        Number of rotated files to keep.
    console:
        When ``True``, attach a stream handler for stdout mirroring file output.
    propagate:
        Whether messages propagate to parent loggers. Disabled by default to
        avoid duplicate log lines when embedding the engine.
    """

    resolved_level = _as_level(level)
    base_dir = Path(log_dir) if log_dir is not None else default_log_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    log_path = base_dir / f"{name.replace('.', '_')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)
    logger.propagate = propagate

    handler_exists = False
    for handler in logger.handlers:
        same_file = Path(handler.baseFilename) == log_path
        if isinstance(handler, RotatingFileHandler) and same_file:
            handler.setLevel(resolved_level)
            handler_exists = True
    if not handler_exists:
        handler = _file_handler(log_path, resolved_level, max_bytes, backup_count)
        logger.addHandler(handler)

    wants_console = console and not any(
        isinstance(h, logging.StreamHandler) for h in logger.handlers
    )
    if wants_console:
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s | %(name)s | %(message)s")
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(resolved_level)
        logger.addHandler(stream_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with default settings."""
    return setup_logger(name)
