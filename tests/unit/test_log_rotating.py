"""Test sui logger a rotazione definiti in ``fair3.engine.utils.log``."""

from __future__ import annotations

import logging
from logging import StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from fair3.engine.utils import log as log_utils


@pytest.fixture(autouse=True)
def isolamento_logger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isola la directory di lavoro e ripulisce gli handler dopo ogni test."""

    monkeypatch.chdir(tmp_path)
    logging.getLogger().handlers = []
    logging.getLogger().setLevel(logging.NOTSET)
    yield
    for logger in list(logging.Logger.manager.loggerDict.values()):
        if isinstance(logger, logging.Logger):
            logger.handlers = []
            logger.setLevel(logging.NOTSET)
    logging.getLogger().handlers = []
    logging.getLogger().setLevel(logging.NOTSET)


def test_default_log_dir_crea_cartelle() -> None:
    """La directory predefinita deve essere creata automaticamente."""

    directory = log_utils.default_log_dir()

    assert directory.exists()
    assert directory.is_dir()
    assert directory.name == "audit"


def test_setup_logger_scrive_file_e_console(tmp_path: Path) -> None:
    """Il logger configurato deve scrivere su file e agganciare la console."""

    logger = log_utils.setup_logger(
        "fair3.pipeline",
        level="INFO",
        log_dir=tmp_path,
        console=True,
    )
    logger.info("messaggio di test")

    for handler in logger.handlers:
        handler.flush()

    log_path = tmp_path / "fair3_pipeline.log"
    contenuto = log_path.read_text(encoding="utf-8")
    assert "messaggio di test" in contenuto

    assert any(
        isinstance(h, StreamHandler) and not isinstance(h, RotatingFileHandler)
        for h in logger.handlers
    )


def test_setup_logger_non_duplicare_handler(tmp_path: Path) -> None:
    """Invocazioni ripetute devono riutilizzare l'handler di file esistente."""

    primo = log_utils.setup_logger("fair3.pipeline", log_dir=tmp_path)
    secondo = log_utils.setup_logger("fair3.pipeline", log_dir=tmp_path)

    rotanti = [h for h in secondo.handlers if isinstance(h, RotatingFileHandler)]
    assert len(rotanti) == 1

    assert primo.handlers == secondo.handlers


def test_get_logger_usa_impostazioni_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L'helper deve delegare a ``setup_logger`` con la directory di default."""

    monkeypatch.chdir(tmp_path)
    logger = log_utils.get_logger("fair3.altro")
    logger.warning("attenzione")

    for handler in logger.handlers:
        handler.flush()

    base = Path("artifacts") / "audit" / "fair3_altro.log"
    assert base.exists()
    assert "attenzione" in base.read_text(encoding="utf-8")
