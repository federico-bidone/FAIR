from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.ecb import ECBFetcher

ECB_CSV = """TIME_PERIOD,OBS_VALUE
2024-01-02,1.1020
2024-01-03,1.0955
"""


@pytest.mark.parametrize("symbol,start_str", [("USD", "2024-01-01")])
def test_ecb_build_url_domain_and_params(symbol: str, start_str: str) -> None:
    f = ECBFetcher()
    start = pd.Timestamp(start_str)
    url = f.build_url(symbol, start)
    # dominio nuovo + path invariato + params invariati
    assert url.startswith("https://data-api.ecb.europa.eu/service/data/EXR/"), url
    remainder = url.split("https://data-api.ecb.europa.eu/service/data/")[1]
    assert Path(remainder.split("?")[0]).parts[0] == "EXR"
    assert f"D.{symbol}.EUR.SP00.A" in url, url
    assert "format=csvdata" in url, url
    assert f"startPeriod={start:%Y-%m-%d}" in url, url


def test_ecb_parse_csv_payload_to_float(monkeypatch: pytest.MonkeyPatch) -> None:
    # mocka il download per non chiamare la rete
    f = ECBFetcher()
    monkeypatch.setattr(ECBFetcher, "_download", lambda self, url, session=None: ECB_CSV)
    artifact = f.fetch(symbols=("USD",), start=pd.Timestamp("2024-01-01"))
    frame = artifact.data
    # validate schema canonico
    assert set(frame.columns) == {"date", "value", "symbol"}
    assert frame["symbol"].unique().tolist() == ["USD"]
    assert pd.api.types.is_float_dtype(frame["value"])
    # check ordinamento per data
    assert frame.sort_values("date")["date"].tolist() == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
