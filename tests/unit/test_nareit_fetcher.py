"""Test per il fetcher Nareit con payload manuali."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.nareit import NareitFetcher


def _fake_excel_frame() -> pd.DataFrame:
    """Costruisce un DataFrame mensile di esempio per gli indici Nareit."""

    return pd.DataFrame(
        {
            "Date": ["2023-12-31", "2024-01-31"],
            "All Equity REITs Total Return": [100.0, 102.5],
            "Mortgage REITs Total Return": [90.0, 91.0],
        }
    )


def test_nareit_fetcher_parsing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Il fetcher deve normalizzare i valori e applicare il filtro `start`."""

    manual_file = tmp_path / "NAREIT_AllSeries.xlsx"
    manual_file.write_bytes(b"placeholder")
    fetcher = NareitFetcher(manual_root=tmp_path, raw_root=tmp_path)
    fake_df = _fake_excel_frame()

    def fake_read_excel(buffer: BytesIO, *, sheet_name: str) -> pd.DataFrame:
        assert isinstance(buffer, BytesIO)
        assert sheet_name == "Monthly"
        return fake_df

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: b"xlsx-bytes")

    artifact = fetcher.fetch(symbols=["all_equity_reit_tr"], start=date(2024, 1, 1))

    assert artifact.metadata["license"] == fetcher.LICENSE
    assert artifact.data["symbol"].tolist() == ["all_equity_reit_tr"]
    assert artifact.data.iloc[0]["date"].date() == date(2024, 1, 31)
    assert pytest.approx(float(artifact.data.iloc[0]["value"]), rel=1e-9) == 102.5


def test_nareit_missing_file(tmp_path: Path) -> None:
    """Se il file manuale non è presente, deve essere sollevato FileNotFoundError."""

    fetcher = NareitFetcher(manual_root=tmp_path, raw_root=tmp_path)
    with pytest.raises(FileNotFoundError):
        fetcher.fetch(symbols=["all_equity_reit_tr"])


def test_nareit_missing_columns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Il parser deve rilevare colonne mancanti nell'Excel manuale."""

    fetcher = NareitFetcher(manual_root=tmp_path, raw_root=tmp_path)
    manual_file = tmp_path / "NAREIT_AllSeries.xlsx"
    manual_file.write_bytes(b"placeholder")

    def fake_read_excel(buffer: BytesIO, *, sheet_name: str) -> pd.DataFrame:
        return pd.DataFrame({"Date": ["2024-01-31"], "Wrong": [1.0]})

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: b"xlsx-bytes")

    with pytest.raises(ValueError, match="Colonne attese mancanti"):
        fetcher.fetch(symbols=["all_equity_reit_tr"])
