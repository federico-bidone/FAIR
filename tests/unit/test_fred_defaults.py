from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from fair3.engine.ingest.fred import FREDFetcher

EXPECTED_DEFAULTS = (
    "DGS01",
    "DGS02",
    "DGS03",
    "DGS05",
    "DGS07",
    "DGS10",
    "DGS20",
    "DGS30",
    "DTB3",
    "CPIAUCSL",
    "T5YIE",
    "T10YIE",
    "DFII5",
    "DFII10",
)

SAMPLE_JSON = """{"observations": [
    {"date": "2024-01-02", "value": "3.14"},
    {"date": "2024-01-03", "value": "."}
]}"""


def test_fred_default_symbol_list() -> None:
    assert FREDFetcher.DEFAULT_SYMBOLS == EXPECTED_DEFAULTS


def test_fred_fetch_uses_extended_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "E" * 32)
    fetcher = FREDFetcher()

    called_symbols: list[str] = []

    def fake_download(url: str, session: object | None = None) -> str:
        parsed = urlparse(url)
        symbol = parse_qs(parsed.query)["series_id"][0]
        called_symbols.append(symbol)
        return SAMPLE_JSON

    monkeypatch.setattr(fetcher, "_download", fake_download)

    artifact = fetcher.fetch(symbols=None, start=None)

    assert tuple(called_symbols) == EXPECTED_DEFAULTS
    assert set(artifact.data["symbol"].unique()) == set(EXPECTED_DEFAULTS)
    assert len(artifact.metadata["requests"]) == len(EXPECTED_DEFAULTS)
    assert pd.api.types.is_float_dtype(artifact.data["value"])
