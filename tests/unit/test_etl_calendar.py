"""Suite di test italiani per ``fair3.engine.etl.calendar``."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.etl import calendar as etl_calendar


def _make_frame(date_strings: list[str]) -> pd.DataFrame:
    """Helper compatto per convertire stringhe in frame con colonna ``date``."""

    return pd.DataFrame({"date": pd.to_datetime(date_strings)})


def test_build_calendar_valida_colonna_date() -> None:
    """Se manca ``date`` deve essere sollevata un'eccezione descrittiva."""

    with pytest.raises(ValueError, match="colonna `date` mancante"):
        etl_calendar.build_calendar({"serie": pd.DataFrame({"wrong": [1, 2, 3]})})


def test_build_calendar_rispettando_limiti_temporali() -> None:
    """Le opzioni ``start`` e ``end`` devono sovrascrivere gli estremi."""

    frames = {"serie": _make_frame(["2020-01-01", "2020-01-10"])}
    calendario = etl_calendar.build_calendar(
        frames,
        freq="B",
        start=datetime(2019, 12, 30),
        end=datetime(2020, 1, 8),
        name="test",
    )
    assert calendario.name == "test"
    assert calendario.dates.min() == pd.Timestamp("2019-12-30")
    assert calendario.dates.max() == pd.Timestamp("2020-01-08")


def test_reindex_frame_allinea_valori_forward_fill() -> None:
    """Il frame riallineato deve riempire i buchi tramite forward fill."""

    calendario = etl_calendar.TradingCalendar(
        name="demo",
        dates=pd.DatetimeIndex(
            pd.to_datetime(["2022-01-03", "2022-01-04", "2022-01-05"]), name="date"
        ),
    )
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-01-03", "2022-01-05"]),
            "symbol": ["ABC", "ABC"],
            "val": [1.0, 2.0],
        }
    )
    riallineato = etl_calendar.reindex_frame(
        frame, calendar=calendario, group_cols=["symbol"], value_cols=["val"]
    )
    assert list(riallineato["val"]) == [1.0, 1.0, 2.0]


def test_trading_calendar_save_scrive_csv(tmp_path: Path) -> None:
    """Il calendario serializzato deve usare formato ISO e preservare le date."""

    calendario = etl_calendar.TradingCalendar(
        name="demo",
        dates=pd.DatetimeIndex(pd.to_datetime(["2021-03-01", "2021-03-02"]), name="date"),
    )
    destinazione = tmp_path / "calendar.csv"
    risultato = calendario.save(destinazione)
    assert risultato == destinazione
    contenuto = destinazione.read_text(encoding="utf-8").splitlines()
    assert contenuto == ["date", "2021-03-01", "2021-03-02"]
