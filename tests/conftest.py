"""Test configuration shared across FAIR-III test modules."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

import pytest


def _insert_repo_root() -> None:
    """Ensure the repository root is available on ``sys.path`` for imports."""

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_insert_repo_root()


def pytest_report_header(config: pytest.Config) -> Iterable[str]:  # pragma: no cover - pytest hook
    """Display helpful debugging context at the start of the test run."""

    root = Path.cwd()
    log_level = os.environ.get("FAIR_LOG_LEVEL", "INFO")
    return [f"FAIR-III repo: {root}", f"FAIR_LOG_LEVEL={log_level}"]


@pytest.fixture(autouse=True)
def _set_verbose_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default pipeline logging to INFO for clearer test diagnostics."""

    monkeypatch.setenv("FAIR_LOG_LEVEL", "INFO")
