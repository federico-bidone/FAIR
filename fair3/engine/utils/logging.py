"""Helper di logging condivisi per l'ecosistema FAIR-III.

Il modulo centralizza la configurazione del logging così che ogni pipeline
produca messaggi coerenti e ad alta verbosità. Tutti gli helper rispettano le
variabili d'ambiente ``FAIR_LOG_LEVEL`` e ``FAIR_LOG_FORMAT``: in questo modo
chi sta facendo debug può controllare l'output senza modificare il codice.
"""

from __future__ import annotations

import logging
import os
from functools import cache
from typing import Final

DEFAULT_FORMAT: Final[str] = "[%(levelname)s] %(name)s: %(message)s"
DEFAULT_LEVEL: Final[str] = "INFO"


@cache
def _determine_level() -> int:
    """Calcola il livello di logging partendo da ``FAIR_LOG_LEVEL``.

    *Cosa fa*: legge il valore della variabile d'ambiente e lo traduce in un
    livello numerico supportato dal modulo :mod:`logging`.
    *Come lo fa*: chiama :func:`logging.getLevelName` e verifica che il
    risultato sia un intero; in caso contrario, torna al valore di default.
    *Perché*: impedisce che errori di configurazione zittiscano i messaggi più
    importanti durante un'analisi.
    """

    level_name = os.environ.get("FAIR_LOG_LEVEL", DEFAULT_LEVEL).upper().strip()
    level = logging.getLevelName(level_name)
    if isinstance(level, int):
        return level
    return logging.INFO


@cache
def _determine_format() -> str:
    """Restituisce la stringa di formato per i messaggi FAIR-III.

    *Cosa fa*: legge ``FAIR_LOG_FORMAT`` e ne usa il valore se non è vuoto.
    *Come lo fa*: recupera il valore, lo ripulisce dagli spazi e torna al
    default quando il risultato è una stringa vuota.
    *Perché*: fornisce un formato coerente tra CLI, test e notebook evitando
    codice duplicato.
    """

    fmt = os.environ.get("FAIR_LOG_FORMAT", DEFAULT_FORMAT).strip()
    return fmt or DEFAULT_FORMAT


def get_stream_logger(name: str) -> logging.Logger:
    """Restituisce un logger di modulo configurato per lo standard FAIR-III.

    *Cosa fa*: costruisce (o recupera) un logger puntato a ``stderr`` con il
    formato e il livello calcolati dagli helper precedenti.
    *Come lo fa*: aggiunge un unico :class:`logging.StreamHandler` al root
    logger alla prima invocazione e riusa il gestore per tutte le chiamate
    successive.
    *Perché*: semplifica l'adozione della verbosità coerente nelle pipeline
    senza costringere i moduli a conoscere la configurazione globale.
    """

    logger = logging.getLogger(name)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.addHandler(logging.StreamHandler())
    formatter = logging.Formatter(_determine_format())
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
    root_logger.setLevel(_determine_level())
    return logger


__all__ = ["get_stream_logger"]
