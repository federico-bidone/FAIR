"""Test italiani per le utilità FX dell'ETL."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.etl import fx


def test_load_fx_rates_unisce_tutte_le_serie() -> None:
    """I record multipli devono essere uniti su base data con outer join."""

    eur_usd = pd.DataFrame(
        {
            "date": ["2023-01-02", "2023-01-03"],
            "value": [1.1, 1.2],
            "symbol": ["EUR/USD", "EUR/USD"],
        }
    )
    eur_gbp = pd.DataFrame(
        {
            "date": ["2023-01-02"],
            "value": [0.9],
            "symbol": ["EUR/GBP"],
        }
    )
    frame = fx.load_fx_rates([eur_usd, eur_gbp], base_currency="EUR")
    assert frame.rates.columns.tolist() == ["USD_to_EUR", "GBP_to_EUR"]
    assert frame.rates.index.min() == pd.Timestamp("2023-01-02")
    assert frame.rates.index.max() == pd.Timestamp("2023-01-03")


def test_fx_frame_lookup_valuta_base() -> None:
    """La valuta base deve tornare una serie costante di 1.0."""

    frame = fx.FXFrame(base_currency="EUR", rates=pd.DataFrame(index=pd.Index([], name="date")))
    serie = frame.lookup("EUR")
    assert serie.empty or (serie == 1.0).all()


def test_convert_to_base_applica_forward_fill() -> None:
    """I tassi devono essere riallineati alle date dei prezzi."""

    dati = pd.DataFrame(
        {
            "date": ["2023-01-02", "2023-01-03"],
            "symbol": ["AAA", "AAA"],
            "currency": ["USD", "USD"],
            "price": [10.0, 11.0],
        }
    )
    fx_frame = fx.FXFrame(
        base_currency="EUR",
        rates=pd.DataFrame(
            {
                "USD_to_EUR": [0.5],
            },
            index=pd.DatetimeIndex(["2023-01-02"], name="date"),
        ),
    )
    convertito = fx.convert_to_base(dati, fx=fx_frame, value_column="price", currency_column="currency")
    assert convertito.loc[0, "price"] == pytest.approx(5.0)
    assert convertito.loc[1, "price"] == pytest.approx(5.5)
    assert set(convertito["currency"].unique()) == {"EUR"}


def test_convert_to_base_convalida_colonne() -> None:
    """Colonne mancanti generano un errore con messaggio in italiano."""

    frame = pd.DataFrame({"date": ["2023-01-01"]})
    dummy_fx = fx.FXFrame(base_currency="EUR", rates=pd.DataFrame())
    with pytest.raises(ValueError, match="colonne mancanti"):
        fx.convert_to_base(frame, fx=dummy_fx)


def test_fx_frame_save_scrive_csv(tmp_path: Path) -> None:
    """La serializzazione deve rispettare l'indice data."""

    dati = pd.DataFrame(
        {"USD_to_EUR": [0.9]}, index=pd.DatetimeIndex(["2023-01-02"], name="date")
    )
    frame = fx.FXFrame(base_currency="EUR", rates=dati)
    destinazione = tmp_path / "fx.csv"
    frame.save(destinazione)
    assert destinazione.read_text(encoding="utf-8").splitlines()[1].startswith("2023-01-02")
