"""Tests for the Tiingo ingest fetcher."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.tiingo import TiingoFetcher

MonkeyPatch = pytest.MonkeyPatch


def test_tiingo_default_symbols() -> None:
    """The fetcher must expose the documented default ticker tuple."""

    assert TiingoFetcher.DEFAULT_SYMBOLS == ("SPY", "VTI")


def test_tiingo_build_url_includes_start_parameter() -> None:
    """`build_url` must normalise the ticker and append the start date."""

    fetcher = TiingoFetcher(api_key="token")
    url = fetcher.build_url("spy", pd.Timestamp("2024-01-05"))
    assert url.startswith("https://api.tiingo.com/tiingo/daily/SPY/prices?")
    assert "startDate=2024-01-05" in url


def test_tiingo_fetch_requires_api_key(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Fetching without a configured API key raises a clear runtime error."""

    monkeypatch.delenv("TIINGO_API_KEY", raising=False)
    fetcher = TiingoFetcher(raw_root=tmp_path, throttle_seconds=0.0)
    with pytest.raises(RuntimeError, match="TIINGO_API_KEY"):
        fetcher.fetch(symbols=["SPY"], as_of=datetime.now(UTC))


def test_tiingo_fetch_parses_json_payload(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """JSON payloads are normalised into the FAIR schema with adjClose values."""

    fetcher = TiingoFetcher(api_key="token", raw_root=tmp_path, throttle_seconds=0.0)
    payload = json.dumps(
        [
            {
                "date": "2024-01-02T00:00:00.000Z",
                "adjClose": 412.34,
                "close": 410.0,
            },
            {
                "date": "2024-01-03T00:00:00.000Z",
                "adjClose": 415.0,
                "close": 414.5,
            },
        ]
    )
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: payload)
    artifact = fetcher.fetch(symbols=["SPY"], as_of=datetime.now(UTC))
    frame = artifact.data
    assert list(frame.columns) == ["date", "value", "symbol"]
    assert frame["symbol"].unique().tolist() == ["SPY"]
    assert frame.iloc[0]["date"] == pd.Timestamp("2024-01-02")
    assert pytest.approx(frame.iloc[1]["value"], rel=1e-9) == 415.0
    assert artifact.metadata["license"] == TiingoFetcher.LICENSE


def test_tiingo_parse_rejects_html_payload() -> None:
    """HTML responses (rate limit/errors) are surfaced as ValueError."""

    fetcher = TiingoFetcher(api_key="token")
    with pytest.raises(ValueError, match="HTML"):
        fetcher.parse("<html>Rate limit</html>", "SPY")
