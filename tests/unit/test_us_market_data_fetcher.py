"""Unit test per il fetcher manuale us-market-data."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.us_market_data import (
    USMarketDataFetcher,
    import_us_market_data_local,
)


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    """Salva il DataFrame in CSV UTF-8 senza indice.

    Args:
        path: Percorso di destinazione.
        frame: Dati da serializzare.

    Returns:
        None.

    Raises:
        OSError: Se l'operazione di scrittura fallisce.
    """

    path.write_text(frame.to_csv(index=False), encoding="utf-8")


def test_import_us_market_data_local_combines_segments(tmp_path: Path) -> None:
    """La funzione deve aggregare CSV multipli calcolando il total return."""

    manual_dir = tmp_path / "us_market_data"
    manual_dir.mkdir()
    first_segment = pd.DataFrame(
        {
            "Date": ["2020-01-02", "2020-01-03"],
            "Close": [10.0, 10.5],
            "Adjusted Close": [1.0, 1.05],
            "Dividend": [0.0, 0.0],
            "Daily Dividend": [0.0, 0.0],
            "Return": [0.0, 0.05],
        }
    )
    second_segment = pd.DataFrame(
        {
            "Date": ["2020-01-06"],
            "Close": [10.25],
            "Adjusted Close": [1.045],
            "Dividend": [0.02],
            "Daily Dividend": [0.0005],
            "Return": [-0.0047619],
        }
    )
    _write_csv(manual_dir / "segment1.csv", first_segment)
    _write_csv(manual_dir / "segment2.csv", second_segment)

    dataset = import_us_market_data_local(manual_dir)
    assert list(dataset.columns) == [
        "date",
        "close",
        "total_return",
        "dividend",
        "daily_return",
    ]
    assert len(dataset) == 3
    # Il total return deve seguire la colonna Adjusted Close.
    assert pytest.approx(dataset.loc[1, "total_return"], rel=1e-6) == 1.05
    # I dividendi giornalieri hanno priorità sul campo aggregato.
    assert pytest.approx(dataset.loc[2, "dividend"], rel=1e-6) == 0.0005
    # Se la colonna Return è presente deve essere riutilizzata.
    assert pytest.approx(dataset.loc[1, "daily_return"], rel=1e-6) == 0.05


def test_us_market_data_fetcher_filters_start_and_metadata(tmp_path: Path) -> None:
    """Il fetcher deve filtrare per data e riportare licenza e percorsi."""

    manual_dir = tmp_path / "us_market_data"
    raw_root = tmp_path / "raw"
    manual_dir.mkdir()
    raw_root.mkdir()

    payload = pd.DataFrame(
        {
            "Date": ["2020-01-02", "2020-01-03", "2020-01-04"],
            "Close": [10.0, 10.5, 10.6],
            "Adjusted Close": [1.0, 1.05, 1.06],
            "Daily Dividend": [0.0, 0.0, 0.001],
            "Return": [0.0, 0.05, 0.0095238],
        }
    )
    _write_csv(manual_dir / "full_data.csv", payload)

    fetcher = USMarketDataFetcher(manual_root=manual_dir, raw_root=raw_root)
    artifact = fetcher.fetch(
        symbols=["sp500_price", "sp500_total_return"],
        start=date(2020, 1, 3),
    )

    assert artifact.metadata["license"] == USMarketDataFetcher.LICENSE
    assert artifact.metadata["requests"] == [
        {"symbol": "sp500_price", "url": f"manual://{manual_dir}"},
        {"symbol": "sp500_total_return", "url": f"manual://{manual_dir}"},
    ]
    values_by_symbol = artifact.data.groupby("symbol")
    price_series = values_by_symbol.get_group("sp500_price")
    total_return_series = values_by_symbol.get_group("sp500_total_return")
    assert price_series["date"].min() >= pd.Timestamp("2020-01-03")
    assert total_return_series["date"].min() >= pd.Timestamp("2020-01-03")
    assert pytest.approx(price_series.iloc[0]["value"], rel=1e-9) == 10.5
    assert pytest.approx(total_return_series.iloc[-1]["value"], rel=1e-9) == 1.06


def test_us_market_data_fetcher_invalid_symbol(tmp_path: Path) -> None:
    """Richiedere un simbolo non supportato deve generare ValueError."""

    manual_dir = tmp_path / "us_market_data"
    manual_dir.mkdir()
    payload = pd.DataFrame(
        {
            "Date": ["2020-01-02"],
            "Close": [10.0],
            "Adjusted Close": [1.0],
        }
    )
    _write_csv(manual_dir / "full.csv", payload)

    fetcher = USMarketDataFetcher(manual_root=manual_dir)
    with pytest.raises(ValueError, match="Unsupported us-market-data symbol"):
        fetcher.fetch(symbols=["dow_index"], start=date(2020, 1, 2))
