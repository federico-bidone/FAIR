from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from fair3.engine.utils.io import ensure_dir

__all__ = ["TradingCalendar", "build_calendar", "reindex_frame"]


@dataclass(slots=True)
class TradingCalendar:
    """Container storing the unified trading calendar used by the ETL."""

    name: str
    dates: pd.DatetimeIndex

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({"date": self.dates})

    def save(self, path: Path) -> Path:
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
    """Create a business-day calendar covering all provided frames."""

    all_dates: set[pd.Timestamp] = set()
    for frame in frames.values():
        if "date" not in frame.columns:
            msg = "expected `date` column in frame"
            raise ValueError(msg)
        all_dates.update(pd.to_datetime(frame["date"]).dt.normalize())

    if not all_dates:
        dates = pd.DatetimeIndex([], name="date")
        return TradingCalendar(name=name, dates=dates)

    min_date = min(all_dates)
    max_date = max(all_dates)
    if start is not None:
        min_date = min_date if min_date <= start else start
    if end is not None:
        max_date = max_date if max_date >= end else end

    full_range = pd.date_range(min_date, max_date, freq=freq, tz="UTC")
    # Normalize to naive timestamps for storage simplicity.
    full_range = full_range.tz_convert(None)
    return TradingCalendar(name=name, dates=full_range)


def reindex_frame(
    frame: pd.DataFrame,
    *,
    calendar: TradingCalendar,
    group_cols: Iterable[str] | None = None,
    value_cols: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Align a frame to the provided calendar using forward fill."""

    if frame.empty:
        return frame

    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    group_cols = list(group_cols or ["symbol"])
    value_cols = list(
        value_cols or [col for col in work.columns if col not in ("date", *group_cols)]
    )

    work = work.set_index(["date", *group_cols]).sort_index()
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
