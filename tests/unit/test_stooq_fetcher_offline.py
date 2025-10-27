from __future__ import annotations

import pytest

from fair3.engine.ingest.registry import BaseCSVFetcher
from fair3.engine.ingest.stooq import StooqFetcher

CSV = "Date,Open,High,Low,Close,Volume\n2024-01-02,10,11,9,10.5,1000\n"
HTML = "<html>bad</html>"


def test_stooq_lowercase_symbol_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    f = StooqFetcher()
    monkeypatch.setattr(StooqFetcher, "_download", lambda self, url, session=None: CSV)
    artifact = f.fetch(symbols=("SPY.US",), start=None)
    df = artifact.data
    assert set(df.columns) == {"date", "value", "symbol", "tz"}
    assert df.loc[0, "symbol"] == "SPY.US"
    assert df.loc[0, "tz"] == "Europe/Warsaw"


def test_stooq_html_error(monkeypatch: pytest.MonkeyPatch) -> None:
    f = StooqFetcher()
    monkeypatch.setattr(StooqFetcher, "_download", lambda self, url, session=None: HTML)
    with pytest.raises(ValueError) as excinfo:
        f.fetch(symbols=("spy.us",), start=None)
    assert "HTML" in str(excinfo.value)


def test_stooq_caches_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_download(
        self: BaseCSVFetcher, url: str, *, session: object | None = None
    ) -> str:  # type: ignore[override]
        nonlocal calls
        calls += 1
        return CSV

    fetcher = StooqFetcher()
    monkeypatch.setattr(BaseCSVFetcher, "_download", fake_download)
    fetcher.fetch(symbols=("spx",), start=None)
    fetcher.fetch(symbols=("SPX",), start=None)
    assert calls == 1


def test_stooq_start_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = (
        "Date,Open,High,Low,Close,Volume\n"
        "2023-12-29,1,1,1,1.5,100\n"
        "2024-01-02,1,1,1,2.5,100\n"
    )

    def fake_download(
        self: StooqFetcher, url: str, *, session: object | None = None
    ) -> str:  # type: ignore[override]
        return sample

    fetcher = StooqFetcher()
    monkeypatch.setattr(StooqFetcher, "_download", fake_download)
    artifact = fetcher.fetch(symbols=("wig20.pl",), start="2024-01-01")
    df = artifact.data
    assert df.shape[0] == 1
    assert df.loc[0, "symbol"] == "WIG20.PL"
