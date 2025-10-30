"""Configurazione Pytest condivisa per FAIR-III con isolamento dei test di rete."""

from __future__ import annotations

import os
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest


def _insert_repo_root() -> None:
    """Assicura che la root del repository sia sul ``sys.path`` per gli import."""

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_insert_repo_root()


def pytest_report_header(config: pytest.Config) -> Iterable[str]:  # pragma: no cover - pytest hook
    """Mostra contesto diagnostico per le esecuzioni di test."""

    root = Path.cwd()
    log_level = os.environ.get("FAIR_LOG_LEVEL", "INFO")
    return [f"FAIR-III repo: {root}", f"FAIR_LOG_LEVEL={log_level}"]


@pytest.fixture(autouse=True)
def _set_verbose_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Imposta il livello di log predefinito a INFO per test più leggibili."""

    monkeypatch.setenv("FAIR_LOG_LEVEL", "INFO")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Aggiunge l'opzione ``--network`` per abilitare esplicitamente i test con chiamate live."""

    parser.addoption(
        "--network",
        action="store_true",
        default=False,
        help="Enable tests that hit live network endpoints or require API tokens.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Registra il marker ``network`` e documenta l'uso nel report Pytest."""

    config.addinivalue_line(
        "markers",
        "network: test che richiede accesso internet/API token; usa --network per abilitarlo.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Applica skip automatico ai test di rete se ``--network`` non è impostato."""

    if config.getoption("--network"):
        return

    skip_marker = pytest.mark.skip(reason="network tests disabilitati; eseguire pytest --network per abilitarli")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip_marker)
