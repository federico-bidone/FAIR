from __future__ import annotations

import pytest

from fair3.engine.ingest.fred import FREDFetcher

HTML_PAYLOAD = "<html>error</html>"


def test_fred_html_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "C" * 32)
    fetcher = FREDFetcher()
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: HTML_PAYLOAD)
    with pytest.raises(ValueError) as excinfo:
        fetcher.fetch(symbols=("DGS10",), start=None)
    assert "non-CSV/non-JSON" in str(excinfo.value)
