"""Filesystem helpers used by the GUI and orchestration layers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

DEFAULT_REPORT_ROOT = Path("artifacts") / "reports"


def create_run_dir(base: str | Path = DEFAULT_REPORT_ROOT) -> Path:
    """Create and return a timestamped report directory."""

    root = Path(base)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = root / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["create_run_dir", "DEFAULT_REPORT_ROOT"]
