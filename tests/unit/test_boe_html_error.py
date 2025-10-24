from __future__ import annotations

import pytest

from fair3.engine.ingest.boe import BOEFetcher

HTML_PAYLOAD = "<html>error</html>"


def test_boe_html_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = BOEFetcher()
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: HTML_PAYLOAD)
    with pytest.raises(ValueError) as excinfo:
        fetcher.fetch(symbols=("IUMGBP",), start=None)
    assert "payload HTML" in str(excinfo.value)
