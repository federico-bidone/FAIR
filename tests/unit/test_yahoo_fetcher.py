"""Test del fetcher Yahoo Finance basato su yfinance."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest

from fair3.engine.ingest.registry import available_sources, create_fetcher


def _sample_csv() -> str:
    return "date,value\n2024-01-02T00:00:00+00:00,100.0\n2024-01-03T00:00:00+00:00,101.0\n"


def test_yahoo_fetcher_registered() -> None:
    """Il registry deve esporre la sorgente ``yahoo``."""

    assert "yahoo" in available_sources()


def test_build_url_and_parse_roundtrip() -> None:
    """La pseudo URL deve includere lo start ISO e il parser deve leggere il CSV."""

    fetcher = create_fetcher("yahoo", delay_seconds=0)
    start = pd.Timestamp("2024-01-01", tz=UTC)
    url = fetcher.build_url("spy", start)
    assert url.startswith("yfinance://SPY")
    frame = fetcher.parse(_sample_csv(), "SPY")
    assert list(frame.columns) == ["date", "value", "symbol"]
    assert frame["symbol"].unique().tolist() == ["SPY"]


def test_fetch_filters_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """`fetch` deve filtrare le osservazioni antecedenti allo start richiesto."""

    fetcher = create_fetcher("yahoo", delay_seconds=0)

    def fake_download(_: str, session: object | None = None) -> str:
        del session
        return _sample_csv()

    monkeypatch.setattr(fetcher, "_download", fake_download)
    artifact = fetcher.fetch(symbols=["SPY"], start=pd.Timestamp("2024-01-03", tz=UTC))
    assert artifact.data["date"].min() >= pd.Timestamp("2024-01-03", tz=UTC)
    assert artifact.metadata["license"].startswith("Yahoo!")


def test_download_enforces_max_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Il download non deve richiedere più di cinque anni di storico."""

    fetcher = create_fetcher("yahoo", delay_seconds=0)
    fixed_now = datetime(2024, 6, 1, tzinfo=UTC)
    monkeypatch.setattr(fetcher, "_now", lambda: fixed_now)

    captured: dict[str, Any] = {}

    def fake_download(**kwargs: object) -> pd.DataFrame:
        captured.update(kwargs)
        index = pd.DatetimeIndex(["2024-05-31"], tz=UTC)
        return pd.DataFrame({"Close": [100.0]}, index=index)

    fake_module = SimpleNamespace(download=fake_download)
    monkeypatch.setattr(fetcher, "_import_yfinance", lambda: fake_module)
    csv_text = fetcher._download("yfinance://SPY?start=2010-01-01T00:00:00+00:00")
    assert "2024-05-31" in csv_text
    assert captured["tickers"] == "SPY"
    assert captured["start"] == "2019-06-01"
    assert captured["end"] == "2024-06-01"


def test_download_requires_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    """Se yfinance manca deve essere sollevato un errore esplicativo."""

    fetcher = create_fetcher("yahoo", delay_seconds=0)

    def missing() -> None:
        raise ModuleNotFoundError("nope")

    monkeypatch.setattr(fetcher, "_import_yfinance", missing)
    with pytest.raises(ModuleNotFoundError):
        fetcher._download("yfinance://SPY")
