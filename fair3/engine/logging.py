"""Structured logging and metrics helpers for FAIR-III."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

CONSOLE_FORMAT: Final[str] = "[%(levelname)s] %(name)s: %(message)s"
DEFAULT_LEVEL: Final[str] = "INFO"
AUDIT_DIR: Final[Path] = Path("artifacts") / "audit"
LOG_PATH: Final[Path] = AUDIT_DIR / "fair3.log"
METRICS_PATH: Final[Path] = AUDIT_DIR / "metrics.jsonl"
JSON_ENV_FLAG: Final[str] = "FAIR_JSON_LOGS"
LEVEL_ENV_FLAG: Final[str] = "FAIR_LOG_LEVEL"


class JsonAuditFormatter(logging.Formatter):
    """Format logging records as single-line JSON payloads."""

    def format(self, record: logging.LogRecord) -> str:
        """Convert a record into a JSON string with audit-friendly fields."""

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
    """Cast arbitrary values to floats when possible."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_audit_dir() -> None:
    """Create the audit directory lazily to support CLI-first usage."""

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_level(level: str | int | None) -> int:
    """Resolve the logging level using CLI/environment preferences."""

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
    """Return True when JSON logging is requested by flag or environment."""

    if explicit:
        return True
    value = os.environ.get(JSON_ENV_FLAG)
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_console_handler(logger: logging.Logger, level: int) -> None:
    """Attach a console handler if the logger does not already have one."""

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
    """Attach a JSON file handler when requested."""

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
    """Configure and return a structured logger for FAIR-III modules."""

    resolved_level = _resolve_level(level)
    logger = logging.getLogger(name)
    logger.setLevel(resolved_level)
    # Propagate to parent loggers to support capture handlers (e.g. pytest caplog)
    # while still emitting through FAIR-III specific handlers.
    logger.propagate = True
    _ensure_console_handler(logger, resolved_level)
    if _json_logging_enabled(json_format):
        _ensure_json_handler(logger, resolved_level)
    return logger


def record_metrics(metric_name: str, value: float, tags: Mapping[str, str] | None = None) -> None:
    """Append a metric observation to the audit metrics log."""

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
    """Reconfigure existing FAIR-III loggers for CLI execution."""

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
