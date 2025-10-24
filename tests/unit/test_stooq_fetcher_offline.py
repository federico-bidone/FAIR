from __future__ import annotations

import pytest

from fair3.engine.ingest.stooq import StooqFetcher

CSV = "Date,Open,High,Low,Close,Volume\n2024-01-02,10,11,9,10.5,1000\n"
HTML = "<html>bad</html>"


def test_stooq_lowercase_symbol_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    f = StooqFetcher()
    monkeypatch.setattr(StooqFetcher, "_download", lambda self, url, session=None: CSV)
    artifact = f.fetch(symbols=("spy.us",), start=None)
    df = artifact.data
    assert set(df.columns) == {"date", "value", "symbol"}


def test_stooq_html_error(monkeypatch: pytest.MonkeyPatch) -> None:
    f = StooqFetcher()
    monkeypatch.setattr(StooqFetcher, "_download", lambda self, url, session=None: HTML)
    with pytest.raises(ValueError) as excinfo:
        f.fetch(symbols=("spy.us",), start=None)
    assert "HTML" in str(excinfo.value)
