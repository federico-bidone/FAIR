from __future__ import annotations

import pandas as pd
import pytest

from fair3.engine.ingest.boe import BOEFetcher

CSV_PAYLOAD = "01/02/2024,1.10\n15/02/2024,1.20\n"


def test_boe_csv_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = BOEFetcher()
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: CSV_PAYLOAD)
    artifact = fetcher.fetch(symbols=("IUMGBP",), start=pd.Timestamp("2024-02-01"))
    df = artifact.data
    assert set(df.columns) == {"date", "value", "symbol"}
    assert df["symbol"].unique().tolist() == ["IUMGBP"]
    assert pd.api.types.is_float_dtype(df["value"])
    assert (df["date"] == pd.Timestamp("2024-02-01")).any()
