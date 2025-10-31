"""Filesystem helpers used by the GUI and orchestration layers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Final

DEFAULT_ARTIFACT_ROOT: Final[Path] = Path("artifacts")
DEFAULT_REPORT_ROOT: Final[Path] = DEFAULT_ARTIFACT_ROOT / "reports"
DEFAULT_LOG_ROOT: Final[Path] = DEFAULT_ARTIFACT_ROOT / "logs"


def run_dir(base: str | Path = DEFAULT_REPORT_ROOT) -> Path:
    """Create and return a timestamped directory rooted under ``base``."""

    root = Path(base)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = root / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


__all__ = ["DEFAULT_ARTIFACT_ROOT", "DEFAULT_LOG_ROOT", "DEFAULT_REPORT_ROOT", "run_dir"]
