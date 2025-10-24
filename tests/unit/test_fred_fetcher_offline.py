from __future__ import annotations

import pandas as pd
import pytest

from fair3.engine.ingest.fred import FREDFetcher

CSV_BOM = "\ufeffDATE,DGS10\n2010-01-04,3.85\n"
CSV_VALUE = "DATE,VALUE\n2010-01-04,3.85\n"
HTML = "<!doctype html><html><body>Rate limited</body></html>"


def test_fred_bom_and_symbol_header(monkeypatch: pytest.MonkeyPatch) -> None:
    f = FREDFetcher()
    monkeypatch.setattr(FREDFetcher, "_download", lambda self, url, session=None: CSV_BOM)
    artifact = f.fetch(symbols=("DGS10",), start=pd.Timestamp("2010-01-01"))
    df = artifact.data
    assert set(df.columns) == {"date", "value", "symbol"}
    assert df["symbol"].unique().tolist() == ["DGS10"]
    assert pd.api.types.is_float_dtype(df["value"])


def test_fred_value_header_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    f = FREDFetcher()
    monkeypatch.setattr(FREDFetcher, "_download", lambda self, url, session=None: CSV_VALUE)
    artifact = f.fetch(symbols=("DGS10",), start=pd.Timestamp("2010-01-01"))
    df = artifact.data
    assert df["symbol"].unique().tolist() == ["DGS10"]
    assert pd.api.types.is_float_dtype(df["value"])


def test_fred_html_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    f = FREDFetcher()
    monkeypatch.setattr(FREDFetcher, "_download", lambda self, url, session=None: HTML)
    with pytest.raises(ValueError) as excinfo:
        f.fetch(symbols=("DGS10",), start=None)
    assert "HTML" in str(excinfo.value)
