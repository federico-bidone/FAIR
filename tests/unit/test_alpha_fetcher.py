"""Tests for the Alpha/q-Factors/Novy-Marx ingest fetcher."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest import create_fetcher
from fair3.engine.ingest.alpha import AlphaFetcher


def test_alpha_fetcher_parses_csv_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """CSV payloads are parsed with scaling and end-of-month alignment."""

    fetcher = AlphaFetcher(raw_root=tmp_path)
    monkeypatch.setattr(
        fetcher,
        "_download",
        lambda url, session=None: "Date,QMJ\n2010-01-01,1.5\n2010-02-01,-0.5\n",
    )
    artifact = fetcher.fetch(symbols=["alpha_qmj"], as_of=datetime.now(UTC))

    frame = artifact.data
    assert list(frame["symbol"].unique()) == ["alpha_qmj"]
    assert frame.loc[0, "date"] == pd.Timestamp("2010-01-31")
    assert pytest.approx(frame.loc[0, "value"], rel=1e-9) == 0.015
    assert artifact.metadata["license"] == AlphaFetcher.LICENSE


def test_alpha_fetcher_parses_html_manual(tmp_path: Path) -> None:
    """HTML tables placed manually are ingested when the file exists."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    html = (
        "<table><tr><th>Date</th><th>Profitability</th></tr>"
        "<tr><td>2012-01-01</td><td>1.0</td></tr>"
        "<tr><td>2012-02-01</td><td>0.5</td></tr></table>"
    )
    (manual_dir / "NovyMarx_Profitability.html").write_text(html, encoding="utf-8")
    fetcher = AlphaFetcher(raw_root=tmp_path / "raw", manual_root=manual_dir)

    artifact = fetcher.fetch(symbols=["novy_profitability"], as_of=datetime.now(UTC))

    assert artifact.data.loc[0, "date"] == pd.Timestamp("2012-01-31")
    assert pytest.approx(artifact.data.loc[0, "value"], rel=1e-9) == 0.01
    assert artifact.metadata["requests"][0]["url"].startswith("manual://")


def test_alpha_fetcher_missing_manual_file(tmp_path: Path) -> None:
    """Missing manual files raise a descriptive FileNotFoundError."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    fetcher = AlphaFetcher(raw_root=tmp_path / "raw", manual_root=manual_dir)

    with pytest.raises(FileNotFoundError, match="NovyMarx_Profitability.html"):
        fetcher.fetch(symbols=["novy_profitability"])


def test_create_fetcher_alpha_passthrough(tmp_path: Path) -> None:
    """`create_fetcher` supports instantiation via registry."""

    fetcher = create_fetcher("alpha", raw_root=tmp_path / "raw")
    assert isinstance(fetcher, AlphaFetcher)
