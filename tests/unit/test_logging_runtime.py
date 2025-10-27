from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from fair3.engine import logging as runtime_logging
from fair3.engine.logging import configure_cli_logging, record_metrics, setup_logger


@pytest.fixture(autouse=True)
def isolate_logging(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Reset logging handlers and run in a temporary working directory."""

    monkeypatch.chdir(tmp_path)
    root = logging.getLogger()
    root.handlers = []
    root.setLevel(logging.NOTSET)
    yield
    for logger in list(logging.Logger.manager.loggerDict.values()):
        if isinstance(logger, logging.Logger):
            logger.handlers = []
            logger.setLevel(logging.NOTSET)
    root.handlers = []
    root.setLevel(logging.NOTSET)


def test_setup_logger_resolves_level_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The helper must honour FAIR_LOG_LEVEL when configuring loggers."""

    monkeypatch.setenv(runtime_logging.LEVEL_ENV_FLAG, "DEBUG")
    logger = setup_logger("fair3.tests.level")

    assert logger.isEnabledFor(logging.DEBUG)
    console_handlers = [h for h in logger.handlers if getattr(h, "_fair3_console", False)]
    assert console_handlers, "expected console handler to be attached"
    assert console_handlers[0].formatter._fmt == runtime_logging.CONSOLE_FORMAT


def test_setup_logger_emits_json_payload(tmp_path: Path) -> None:
    """When json_format=True the audit file must contain structured entries."""

    logger = setup_logger("fair3.tests.json", json_format=True)
    logger.info(
        "download complete",
        extra={
            "process_time_ms": 12.5,
            "bytes_downloaded": 1024,
            "rows_processed": 3,
            "ratelimit_event": True,
        },
    )
    for handler in logger.handlers:
        handler.flush()

    audit_path = runtime_logging.LOG_PATH
    payloads = [
        json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line
    ]
    assert payloads, "expected at least one JSON log line"
    record = payloads[0]
    assert record["message"] == "download complete"
    assert record["process_time_ms"] == pytest.approx(12.5)
    assert record["bytes_downloaded"] == pytest.approx(1024.0)
    assert record["rows_processed"] == pytest.approx(3.0)
    assert record["ratelimit_event"] is True


def test_record_metrics_appends_jsonl() -> None:
    """Metrics helper must append JSON lines with tags."""

    record_metrics("ingest_rows", 42, {"source": "ecb"})
    contents = runtime_logging.METRICS_PATH.read_text(encoding="utf-8")
    lines = [json.loads(line) for line in contents.splitlines() if line]
    assert lines and lines[0]["metric"] == "ingest_rows"
    assert lines[0]["value"] == pytest.approx(42.0)
    assert lines[0]["tags"] == {"source": "ecb"}


def test_configure_cli_logging_updates_existing_loggers() -> None:
    """Existing FAIR-III loggers should gain JSON handlers when requested."""

    first = setup_logger("fair3.engine.sample")
    assert not any(getattr(h, "_fair3_json", False) for h in first.handlers)

    configure_cli_logging(json_logs=True)
    assert any(getattr(h, "_fair3_json", False) for h in first.handlers)
