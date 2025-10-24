from __future__ import annotations

import pandas as pd
import pytest

from fair3.engine.ingest.fred import FREDFetcher

SAMPLE_JSON = """{"observations": [
    {"date": "2024-01-01", "value": "1.5"},
    {"date": "2024-01-02", "value": "."},
    {"date": "invalid", "value": "2.0"}
]}"""


def test_fred_json_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "A" * 32)
    fetcher = FREDFetcher()
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: SAMPLE_JSON)
    artifact = fetcher.fetch(symbols=("GNPCA",), start=pd.Timestamp("2024-01-01"))
    df = artifact.data
    assert set(df.columns) == {"date", "value", "symbol"}
    assert df["symbol"].unique().tolist() == ["GNPCA"]
    assert pd.api.types.is_float_dtype(df["value"])
    assert pd.isna(df.loc[df["date"] == pd.Timestamp("2024-01-02"), "value"]).all()
    assert (df["date"] == pd.Timestamp("2024-01-01")).any()
