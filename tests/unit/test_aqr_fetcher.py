"""Tests for the AQR ingest fetcher."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest import create_fetcher
from fair3.engine.ingest.aqr import AQRFetcher


def test_aqr_fetcher_parses_manual_csv(tmp_path: Path) -> None:
    """Manual CSV files are parsed, scaled, and timestamped deterministically."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    raw_root = tmp_path / "raw"
    (manual_dir / "QMJ_US.csv").write_text(
        "Date,QMJ\n2010-01-01,1.2\n2010-02-01,-0.5\n",
        encoding="utf-8",
    )
    fetcher = AQRFetcher(raw_root=raw_root, manual_root=manual_dir)
    artifact = fetcher.fetch(symbols=["qmj_us"], as_of=datetime.now(UTC))

    frame = artifact.data
    assert list(frame["symbol"].unique()) == ["qmj_us"]
    assert frame.loc[0, "date"] == pd.Timestamp("2010-01-31")
    assert pytest.approx(frame.loc[0, "value"], rel=1e-9) == 0.012
    assert artifact.metadata["requests"][0]["url"].startswith("manual://")
    assert artifact.path.exists()


def test_aqr_create_fetcher_supports_manual_kwargs(tmp_path: Path) -> None:
    """`create_fetcher` must forward manual root overrides to the fetcher."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    fetcher = create_fetcher("aqr", raw_root=tmp_path / "raw", manual_root=manual_dir)

    assert isinstance(fetcher, AQRFetcher)
    assert fetcher.manual_root == manual_dir


def test_aqr_fetcher_missing_file(tmp_path: Path) -> None:
    """Missing manual files trigger a descriptive FileNotFoundError."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    fetcher = AQRFetcher(raw_root=tmp_path / "raw", manual_root=manual_dir)

    with pytest.raises(FileNotFoundError, match="QMJ_US.csv"):
        fetcher.fetch(symbols=["qmj_us"])


def test_aqr_fetcher_rejects_html_payload(tmp_path: Path) -> None:
    """HTML payloads (login pages, rate limits) are rejected explicitly."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    (manual_dir / "QMJ_US.csv").write_text("<html>blocked</html>", encoding="utf-8")
    fetcher = AQRFetcher(raw_root=tmp_path / "raw", manual_root=manual_dir)

    with pytest.raises(ValueError, match="HTML payload"):
        fetcher.fetch(symbols=["qmj_us"], as_of=datetime.now(UTC))
