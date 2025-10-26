"""Test per gli helper di logging condivisi."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from fair3.engine.utils import logging as logging_utils


@contextmanager
def ripristina_env(**updates: str) -> Iterator[None]:
    """Modifica temporaneamente le variabili d'ambiente per il test."""

    vecchi = {}
    try:
        for chiave, valore in updates.items():
            vecchi[chiave] = os.environ.get(chiave)
            os.environ[chiave] = valore
        yield
    finally:
        for chiave, _valore in updates.items():
            if vecchi[chiave] is None:
                os.environ.pop(chiave, None)
            else:
                os.environ[chiave] = vecchi[chiave]


@pytest.fixture(autouse=True)
def pulisci_logger() -> Iterator[None]:
    """Ripulisce gli handler del root logger per garantire isolamento."""

    logging.getLogger().handlers = []
    logging.getLogger().setLevel(logging.NOTSET)
    logging_utils._determine_level.cache_clear()  # type: ignore[attr-defined]
    logging_utils._determine_format.cache_clear()  # type: ignore[attr-defined]
    yield
    logging.getLogger().handlers = []
    logging.getLogger().setLevel(logging.NOTSET)
    logging_utils._determine_level.cache_clear()  # type: ignore[attr-defined]
    logging_utils._determine_format.cache_clear()  # type: ignore[attr-defined]


def test_get_stream_logger_imposta_handler_e_formato() -> None:
    """Il logger deve agganciare uno stream handler con formato personalizzato."""

    with ripristina_env(FAIR_LOG_FORMAT="%(message)s"):
        logger = logging_utils.get_stream_logger("prova")
        assert logging.getLogger().handlers, "Il root logger deve avere almeno un handler"
        handler = logging.getLogger().handlers[0]
        assert isinstance(handler, logging.StreamHandler)
        assert handler.formatter._fmt == "%(message)s"
        logger.info("ping")


def test_get_stream_logger_rispetta_livello_da_env() -> None:
    """Il livello configurato via env deve essere tradotto correttamente."""

    with ripristina_env(FAIR_LOG_LEVEL="DEBUG"):
        logger = logging_utils.get_stream_logger("prova")
        assert logger.isEnabledFor(logging.DEBUG)


def test_get_stream_logger_valore_env_non_valido() -> None:
    """Valori errati non devono rompere la configurazione di default."""

    with ripristina_env(FAIR_LOG_LEVEL="NONESISTE"):
        logger = logging_utils.get_stream_logger("prova")
        assert logger.isEnabledFor(logging.INFO)
