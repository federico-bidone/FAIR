from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest import registry
from fair3.engine.ingest.alphavantage import AlphaVantageFXFetcher


def _sample_csv() -> str:
    return "timestamp,open,high,low,close\n2024-01-02,1.10,1.20,1.00,1.15\n"


def test_build_url_parses_symbol_without_api_key() -> None:
    fetcher = AlphaVantageFXFetcher(api_key="demo", throttle_seconds=0.0)
    url = fetcher.build_url("usd", None)
    assert url.startswith(fetcher.BASE_URL)
    assert "from_symbol=USD" in url
    assert "to_symbol=EUR" in url
    assert "apikey" not in url


def test_build_url_supports_compact_pair() -> None:
    fetcher = AlphaVantageFXFetcher(api_key="demo", throttle_seconds=0.0)
    url = fetcher.build_url("gbpusd", None)
    assert "from_symbol=GBP" in url
    assert "to_symbol=USD" in url


def test_parse_csv_returns_dataframe() -> None:
    fetcher = AlphaVantageFXFetcher(api_key="demo", throttle_seconds=0.0)
    frame = fetcher.parse(_sample_csv(), "USD")
    assert list(frame.columns) == ["date", "value", "symbol"]
    assert frame.loc[0, "symbol"] == "USD"
    assert pd.Timestamp("2024-01-02") == frame.loc[0, "date"]
    assert pytest.approx(frame.loc[0, "value"], rel=1e-9) == 1.15


def test_parse_json_rate_limit() -> None:
    fetcher = AlphaVantageFXFetcher(api_key="demo", throttle_seconds=0.0)
    payload = "{" '"Note": "Thank you for using Alpha Vantage"' "}"
    with pytest.raises(ValueError, match="rate limit"):
        fetcher.parse(payload, "USD")


def test_download_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    fetcher = AlphaVantageFXFetcher(throttle_seconds=0.0)
    with pytest.raises(RuntimeError, match="API key missing"):
        fetcher._download("https://example.invalid/query")


def test_download_appends_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = AlphaVantageFXFetcher(api_key="secret", throttle_seconds=0.0)
    captured: dict[str, str] = {}

    def fake_download(
        self: registry.BaseCSVFetcher, url: str, session: object | None = None
    ) -> str:  # type: ignore[override]
        captured["url"] = url
        return _sample_csv()

    monkeypatch.setattr(registry.BaseCSVFetcher, "_download", fake_download, raising=False)
    payload = fetcher._download(
        "https://www.alphavantage.co/query?function=FX_DAILY&from_symbol=USD&to_symbol=EUR"
    )
    assert "apikey=secret" in captured["url"]
    assert payload == _sample_csv()


def test_fetch_masks_api_key_in_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = AlphaVantageFXFetcher(api_key="secret", throttle_seconds=0.0, raw_root=tmp_path)
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: _sample_csv())
    artifact = fetcher.fetch(symbols=["USD"], start=date(2024, 1, 1))
    request_url = artifact.metadata["requests"][0]["url"]
    assert "apikey" not in request_url
    assert artifact.data.loc[0, "symbol"] == "USD"


def test_invalid_symbol_raises() -> None:
    fetcher = AlphaVantageFXFetcher(api_key="demo", throttle_seconds=0.0)
    with pytest.raises(ValueError):
        fetcher.build_url("US", None)
