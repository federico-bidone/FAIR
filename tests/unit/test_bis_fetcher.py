"""Unit tests for the BIS REER/NEER ingest fetcher."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.bis import BISFetcher

MonkeyPatch = pytest.MonkeyPatch


def test_bis_default_symbols() -> None:
    """The fetcher must expose the documented default tuple."""

    assert BISFetcher.DEFAULT_SYMBOLS == ("REER:USA:M", "NEER:USA:M")


def test_bis_build_url_formats_start_period() -> None:
    """Monthly start dates are rounded and encoded in the query string."""

    fetcher = BISFetcher()
    url = fetcher.build_url("REER:ITA:M", pd.Timestamp("2005-03-17"))
    assert url.startswith("https://stats.bis.org/api/v1/data/REER/M.ITA?")
    assert "format=csv" in url
    assert "detail=dataonly" in url
    assert "startPeriod=2005-03" in url


def test_bis_parse_normalises_payload(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """CSV payloads with mixed headers are normalised into the FAIR schema."""

    fetcher = BISFetcher(raw_root=tmp_path)
    payload = (
        "Frequency, Reference area, Indicator, Time Period, OBS_VALUE\n"
        "M, USA, REER, 1994-01, 102.3\n"
        "M, USA, REER, 1994-02, 103.0\n"
    )
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: payload)
    artifact = fetcher.fetch(symbols=["REER:USA:M"], as_of=datetime.now(UTC))
    frame = artifact.data
    assert list(frame["symbol"].unique()) == ["REER:USA:M"]
    assert frame["date"].tolist() == [pd.Timestamp("1994-01-01"), pd.Timestamp("1994-02-01")]
    assert pytest.approx(frame["value"].tolist(), rel=1e-9) == [102.3, 103.0]
    assert artifact.metadata["license"] == BISFetcher.LICENSE


def test_bis_parse_rejects_html_payload() -> None:
    """HTML responses (rate limits) raise a descriptive ValueError."""

    fetcher = BISFetcher()
    with pytest.raises(ValueError, match="payload HTML"):
        fetcher.parse("<html>limited</html>", "REER:USA:M")


def test_bis_parse_validates_symbol_format() -> None:
    """Symbols must match the <dataset>:<area>:<freq> format."""

    fetcher = BISFetcher()
    with pytest.raises(ValueError, match="<dataset>:<area>:<freq>"):
        fetcher.build_url("REER-ITA-M", None)
