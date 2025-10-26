from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from fair3.engine.logging import setup_logger


@pytest.fixture(autouse=True)
def isolate_loggers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Ensure logging handlers do not leak across tests."""

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


def test_setup_logger_idempotent_for_same_name() -> None:
    """Creating a logger multiple times must not attach duplicate handlers."""

    first = setup_logger("fair3.sample", json_format=True)
    second = setup_logger("fair3.sample", json_format=True)

    assert first.handlers == second.handlers
    json_handlers = [
        handler for handler in second.handlers if getattr(handler, "_fair3_json", False)
    ]
    assert len(json_handlers) == 1


def test_separate_loggers_share_json_file() -> None:
    """Different loggers should append to the same audit file without conflicts."""

    alpha = setup_logger("fair3.alpha", json_format=True)
    beta = setup_logger("fair3.beta", json_format=True)

    assert alpha.handlers != [] and beta.handlers != []
    alpha.info("alpha")
    beta.info("beta")
    for handler in alpha.handlers + beta.handlers:
        handler.flush()

    lines = Path("artifacts") / "audit" / "fair3.log"
    content = lines.read_text(encoding="utf-8")
    assert "alpha" in content and "beta" in content
