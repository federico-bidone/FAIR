from __future__ import annotations

"""Utility di calendario per armonizzare i dataset ETL in formato PIT."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from fair3.engine.utils.io import ensure_dir

__all__ = ["TradingCalendar", "build_calendar", "reindex_frame"]


@dataclass(slots=True)
class TradingCalendar:
    """Contenitore del calendario di negoziazione unificato usato dall'ETL.

    Manteniamo le date già normalizzate (senza timezone) per evitare sorprese
    durante la serializzazione su disco e per facilitare il confronto nei
    test.  Il calendario funge da riferimento comune per tutti i flussi che
    alimentano il pannello dati.
    """

    name: str
    dates: pd.DatetimeIndex

    def to_frame(self) -> pd.DataFrame:
        """Restituisce il calendario come `DataFrame` con colonna `date`.

        È utile nei test e quando vogliamo esportare il calendario per audit.
        """

        return pd.DataFrame({"date": self.dates})

    def save(self, path: Path) -> Path:
        """Salva il calendario su CSV con formattazione ISO e ritorna il path."""

        ensure_dir(path.parent)
        frame = self.to_frame()
        frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
        frame.to_csv(path, index=False)
        return path


def build_calendar(
    frames: Mapping[str, pd.DataFrame],
    *,
    freq: str = "B",
    start: datetime | None = None,
    end: datetime | None = None,
    name: str = "union",
) -> TradingCalendar:
    """Costruisce un calendario a giorni lavorativi che copre tutti i frame.

    Questa funzione armonizza le finestre temporali provenienti da ingest
    differenti: normalizziamo le date, controlliamo la presenza della colonna
    `date` e applichiamo eventuali limiti superiori/inferiori passati come
    parametri.  Restituiamo sempre un `TradingCalendar` anche quando gli input
    sono vuoti, così il chiamante non deve gestire `None`.
    """

    all_dates: set[pd.Timestamp] = set()
    # Iteriamo tutti i frame forniti e accumuliamo le date normalizzate; il
    # set ci protegge da duplicati e rende il merge insensibile all'ordine.
    for frame in frames.values():
        if "date" not in frame.columns:
            msg = "colonna `date` mancante nel frame"
            raise ValueError(msg)
        all_dates.update(pd.to_datetime(frame["date"]).dt.normalize())

    # Senza date non costruiamo range artificiosi: restituiamo un calendario
    # vuoto così che il chiamante possa decidere come procedere.
    if not all_dates:
        dates = pd.DatetimeIndex([], name="date")
        return TradingCalendar(name=name, dates=dates)

    min_date = min(all_dates)
    max_date = max(all_dates)
    if start is not None:
        min_date = min_date if min_date <= start else start
    if end is not None:
        max_date = end if end <= max_date else max_date

    full_range = pd.date_range(min_date, max_date, freq=freq, tz="UTC")
    # Normalizziamo a timestamp naive: evitare timezone riduce la complessità
    # durante la serializzazione e riflette l'uso interno dei dati.
    full_range = full_range.tz_convert(None)
    return TradingCalendar(name=name, dates=full_range)


def reindex_frame(
    frame: pd.DataFrame,
    *,
    calendar: TradingCalendar,
    group_cols: Iterable[str] | None = None,
    value_cols: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Allinea un `DataFrame` al calendario usando forward fill sui valori.

    Il raggruppamento per simbolo (o altra chiave custom) evita contaminazioni
    tra asset, mentre la costruzione del template MultiIndex garantisce che
    tutte le date del calendario vengano materializzate.  I valori mancanti
    vengono colmati con `ffill`, assumendo che i dati siano piecewise constant
    tra una data e la successiva, ipotesi coerente con i prezzi di mercato.
    """

    if frame.empty:
        return frame

    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    group_cols = list(group_cols or ["symbol"])
    value_cols = list(
        value_cols or [col for col in work.columns if col not in ("date", *group_cols)]
    )

    work = work.set_index(["date", *group_cols]).sort_index()
    # Costruiamo il template MultiIndex per materializzare tutte le date del
    # calendario per ogni gruppo, così da colmare i buchi con forward fill.
    template = (
        pd.MultiIndex.from_product(
            [calendar.dates, work.index.levels[1]], names=["date", *group_cols]
        )
        if len(group_cols) == 1
        else work.index
    )
    work = work.reindex(template)
    group_levels = list(range(1, work.index.nlevels))
    work[value_cols] = work.groupby(level=group_levels)[value_cols].ffill()
    work = work.reset_index()
    return work
