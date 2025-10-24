from __future__ import annotations

import io
import zipfile

import pandas as pd
import pytest

from fair3.engine.ingest.fred import FREDFetcher


def build_zip_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "observations.csv",
            "date,value\n2024-01-01,1.0\n2024-01-02,.\n",
        )
    return buffer.getvalue()


ZIP_PAYLOAD = build_zip_payload()


def test_fred_csv_zip_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "B" * 32)
    fetcher = FREDFetcher(file_type="csv")
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: ZIP_PAYLOAD)
    artifact = fetcher.fetch(symbols=("DGS10",), start=None)
    df = artifact.data
    assert set(df.columns) == {"date", "value", "symbol"}
    assert df["symbol"].unique().tolist() == ["DGS10"]
    assert pd.api.types.is_float_dtype(df["value"])
    assert pd.isna(df.loc[df["date"] == pd.Timestamp("2024-01-02"), "value"]).all()
