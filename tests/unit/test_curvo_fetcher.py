"""Unit test per il fetcher manuale Curvo.eu."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.curvo import CurvoFetcher, CurvoInstrumentSpec


def test_curvo_fetcher_converts_to_eur_and_total_return(tmp_path: Path) -> None:
    """Verifica la conversione USD→EUR e il calcolo del total return."""

    manual_root = tmp_path / "curvo"
    manual_root.mkdir()
    fx_root = manual_root / "fx"
    fx_root.mkdir()

    data = pd.DataFrame(
        {
            "Date": ["2024-01-02", "2024-01-03"],
            "Price": [100.0, 102.0],
            "Dividend": [0.0, 1.0],
        }
    )
    data.to_csv(manual_root / "msci_world_net.csv", index=False)
    fx = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "rate": [0.9, 0.92],
        }
    )
    fx.to_csv(fx_root / "USD_EUR.csv", index=False)

    spec = CurvoInstrumentSpec(
        symbol="CURVO_MSCI_WORLD_NET_TR",
        filename="msci_world_net.csv",
        currency="USD",
        date_column="Date",
        price_column="Price",
        dividend_column="Dividend",
    )
    fetcher = CurvoFetcher(
        manual_root=manual_root,
        fx_root=fx_root,
        instrument_specs=[spec],
        raw_root=tmp_path / "raw",
    )

    artifact = fetcher.fetch(start="2024-01-03")

    assert artifact.data["symbol"].tolist() == ["CURVO_MSCI_WORLD_NET_TR"]
    assert artifact.data["date"].tolist() == [pd.Timestamp("2024-01-03")]
    assert artifact.data["value"].tolist() == pytest.approx([94.76], rel=1e-4)
    request_meta = artifact.metadata["requests"][0]
    assert request_meta["currency"] == "USD"
    assert request_meta["fx_file"].endswith("USD_EUR.csv")


def test_curvo_fetcher_missing_fx_file(tmp_path: Path) -> None:
    """Un dataset in valuta estera senza FX locale deve sollevare errore."""

    manual_root = tmp_path / "curvo"
    manual_root.mkdir()
    data = pd.DataFrame(
        {
            "Date": ["2024-01-02"],
            "Price": [100.0],
            "Dividend": [0.0],
        }
    )
    data.to_csv(manual_root / "msci_world_net.csv", index=False)
    spec = CurvoInstrumentSpec(
        symbol="CURVO_MSCI_WORLD_NET_TR",
        filename="msci_world_net.csv",
        currency="USD",
        date_column="Date",
        price_column="Price",
        dividend_column="Dividend",
    )
    fetcher = CurvoFetcher(
        manual_root=manual_root,
        instrument_specs=[spec],
        raw_root=tmp_path / "raw",
    )

    with pytest.raises(FileNotFoundError, match="USD_EUR.csv"):
        fetcher.fetch()


def test_curvo_fetcher_handles_eur_currency(tmp_path: Path) -> None:
    """I dataset denominati in EUR non richiedono file FX dedicati."""

    manual_root = tmp_path / "curvo"
    manual_root.mkdir()
    data = pd.DataFrame(
        {
            "Date": ["2024-01-02", "2024-01-03"],
            "Price": [50.0, 51.0],
            "Dividend": [0.0, 0.0],
        }
    )
    data.to_csv(manual_root / "msci_emu_net.csv", index=False)
    spec = CurvoInstrumentSpec(
        symbol="CURVO_MSCI_EMU_NET_TR",
        filename="msci_emu_net.csv",
        currency="EUR",
        date_column="Date",
        price_column="Price",
        dividend_column="Dividend",
    )
    fetcher = CurvoFetcher(
        manual_root=manual_root,
        instrument_specs=[spec],
        raw_root=tmp_path / "raw",
    )

    artifact = fetcher.fetch()

    assert artifact.data["value"].tolist() == pytest.approx([50.0, 51.0], rel=1e-9)
    assert artifact.metadata["requests"][0]["currency"] == "EUR"
