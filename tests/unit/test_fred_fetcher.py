from __future__ import annotations

import pandas as pd
import pytest

from fair3.engine.ingest.fred import FREDFetcher

# caso 1: header contiene il simbolo → usa colonna col simbolo
CSV_WITH_SYMBOL = "DATE,SP500\n2024-01-02,4760.5\n2024-01-03,4740.1\n"
# caso 2: header classico → 'VALUE'
CSV_WITH_VALUE = "DATE,VALUE\n2024-01-02,4.10\n2024-01-03,4.20\n"


def test_fred_parse_header_symbol_column(monkeypatch: pytest.MonkeyPatch) -> None:
    f = FREDFetcher()
    monkeypatch.setattr(FREDFetcher, "_download", lambda self, url, session=None: CSV_WITH_SYMBOL)
    artifact = f.fetch(symbols=("SP500",), start=pd.Timestamp("2024-01-01"))
    df = artifact.data
    assert set(df.columns) == {"date", "value", "symbol"}
    assert df["symbol"].unique().tolist() == ["SP500"]
    assert pd.api.types.is_float_dtype(df["value"])


def test_fred_parse_header_value_column(monkeypatch: pytest.MonkeyPatch) -> None:
    f = FREDFetcher()
    monkeypatch.setattr(FREDFetcher, "_download", lambda self, url, session=None: CSV_WITH_VALUE)
    artifact = f.fetch(symbols=("DGS10",), start=pd.Timestamp("2024-01-01"))
    df = artifact.data
    assert df["symbol"].unique().tolist() == ["DGS10"]
    assert pd.api.types.is_float_dtype(df["value"])
