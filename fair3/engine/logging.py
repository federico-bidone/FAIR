"""Utility per logging strutturato e metriche dedicate a FAIR-III."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from fair3.engine.infra.paths import DEFAULT_LOG_ROOT

CONSOLE_FORMAT: Final[str] = "[%(levelname)s] %(name)s: %(message)s"
DEFAULT_LEVEL: Final[str] = "INFO"
AUDIT_DIR: Final[Path] = DEFAULT_LOG_ROOT
LOG_PATH: Final[Path] = AUDIT_DIR / "fair3.log"
METRICS_PATH: Final[Path] = AUDIT_DIR / "metrics.jsonl"
JSON_ENV_FLAG: Final[str] = "FAIR_JSON_LOGS"
LEVEL_ENV_FLAG: Final[str] = "FAIR_LOG_LEVEL"


class JsonAuditFormatter(logging.Formatter):
    """Formatta i record di log come payload JSON monoriga."""

    def format(self, record: logging.LogRecord) -> str:
        """Converte un record in una stringa JSON con campi adatti all'audit."""

        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        payload = {
            "timestamp": timestamp,
            "level": record.levelname,
            "source": record.name,
            "message": record.getMessage(),
            "process_time_ms": _coerce_number(getattr(record, "process_time_ms", None)),
            "bytes_downloaded": _coerce_number(getattr(record, "bytes_downloaded", None)),
            "rows_processed": _coerce_number(getattr(record, "rows_processed", None)),
            "ratelimit_event": bool(getattr(record, "ratelimit_event", False)),
        }
        return json.dumps(payload, ensure_ascii=False)


def _coerce_number(value: object) -> float | None:
    """Converte valori arbitrari in float quando possibile."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_audit_dir() -> None:
    """Crea la cartella di audit in modo pigro per supportare l'uso da CLI."""

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_level(level: str | int | None) -> int:
    """Determina il livello di log usando preferenze CLI o d'ambiente."""

    env_level = os.environ.get(LEVEL_ENV_FLAG)
    if env_level:
        candidate = env_level.strip().upper()
    elif isinstance(level, str):
        candidate = level.strip().upper()
    elif isinstance(level, int):
        return int(level)
    else:
        candidate = DEFAULT_LEVEL
    resolved = logging.getLevelName(candidate)
    return int(resolved) if isinstance(resolved, int) else logging.INFO


def _json_logging_enabled(explicit: bool) -> bool:
    """Restituisce ``True`` quando il logging JSON è richiesto da flag o ambiente."""

    if explicit:
        return True
    value = os.environ.get(JSON_ENV_FLAG)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_console_handler(logger: logging.Logger, level: int) -> None:
    """Aggancia un handler console se il logger non ne possiede già uno."""

    for handler in logger.handlers:
        if getattr(handler, "_fair3_console", False):
            handler.setLevel(level)
            return
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    stream_handler._fair3_console = True  # type: ignore[attr-defined]
    logger.addHandler(stream_handler)


def _ensure_json_handler(logger: logging.Logger, level: int) -> None:
    """Collega un handler JSON su file quando richiesto."""

    for handler in logger.handlers:
        if getattr(handler, "_fair3_json", False):
            handler.setLevel(level)
            return
    _ensure_audit_dir()
    json_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    json_handler.setLevel(level)
    json_handler.setFormatter(JsonAuditFormatter())
    json_handler._fair3_json = True  # type: ignore[attr-defined]
    logger.addHandler(json_handler)


def setup_logger(
    name: str,
    json_format: bool = False,
    level: str | int | None = None,
) -> logging.Logger:
    """Configura e restituisce un logger strutturato per i moduli FAIR-III."""

    resolved_level = _resolve_level(level)
    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)
    # Propaghiamo ai logger genitori così da supportare gli handler di cattura
    # (ad esempio ``pytest caplog``) mantenendo comunque gli handler specifici FAIR-III.
    logger.propagate = True
    _ensure_console_handler(logger, resolved_level)
    if _json_logging_enabled(json_format):
        _ensure_json_handler(logger, resolved_level)
    return logger


def record_metrics(metric_name: str, value: float, tags: Mapping[str, str] | None = None) -> None:
    """Aggiunge un'osservazione di metrica al log di audit delle metriche."""

    _ensure_audit_dir()
    payload = {
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "metric": metric_name,
        "value": float(value),
        "tags": dict(tags or {}),
    }
    with METRICS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def configure_cli_logging(json_logs: bool, level: str | int | None = None) -> None:
    """Riconfigura i logger FAIR-III esistenti per l'esecuzione via CLI."""

    if json_logs:
        os.environ[JSON_ENV_FLAG] = "1"
    else:
        os.environ.pop(JSON_ENV_FLAG, None)
    for name, logger in logging.Logger.manager.loggerDict.items():
        if not isinstance(logger, logging.Logger):
            continue
        if not name.startswith("fair3"):
            continue
        setup_logger(name, json_format=json_logs, level=level)
    setup_logger("fair3", json_format=json_logs, level=level)


__all__ = ["setup_logger", "record_metrics", "configure_cli_logging"]
