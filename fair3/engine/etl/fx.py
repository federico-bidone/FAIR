from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fair3.engine.utils.io import ensure_dir

__all__ = ["FXFrame", "load_fx_rates", "convert_to_base"]


@dataclass(slots=True)
class FXFrame:
    """Container holding FX rates relative to the base currency."""

    base_currency: str
    rates: pd.DataFrame

    def lookup(self, currency: str) -> pd.Series:
        if currency == self.base_currency:
            return pd.Series(1.0, index=self.rates.index)
        column = f"{currency}_to_{self.base_currency}"
        if column not in self.rates.columns:
            raise KeyError(f"missing FX column {column}")
        return self.rates[column]

    def save(self, path: Path) -> Path:
        ensure_dir(path.parent)
        frame = self.rates.copy()
        frame.index = frame.index.strftime("%Y-%m-%d")
        frame.to_csv(path)
        return path


def load_fx_rates(records: Iterable[pd.DataFrame], base_currency: str) -> FXFrame:
    """Build FX rate table from raw ingest records."""

    frames: list[pd.DataFrame] = []
    for record in records:
        if {"date", "value", "symbol"} - set(record.columns):
            msg = "record must contain date/value/symbol columns"
            raise ValueError(msg)
        symbol = record["symbol"].iat[0]
        frame = record.copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        frame = frame.rename(columns={"value": symbol})[["date", symbol]]
        frames.append(frame)

    if frames:
        merged = frames[0]
        for frame in frames[1:]:
            merged = merged.merge(frame, on="date", how="outer")
        merged = merged.sort_values("date").set_index("date")
    else:
        merged = pd.DataFrame(index=pd.DatetimeIndex([], name="date"))

    return FXFrame(base_currency=base_currency, rates=merged)


def convert_to_base(
    frame: pd.DataFrame,
    *,
    fx: FXFrame,
    value_column: str = "price",
    currency_column: str = "currency",
) -> pd.DataFrame:
    """Convert the provided price column into the FX base currency."""

    if frame.empty:
        return frame
    required = {"date", currency_column, value_column}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"frame missing columns: {missing}")

    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    work = work.sort_values(["symbol", "date"])  # type: ignore[arg-type]
    factors = []
    for currency, sub in work.groupby(currency_column):
        rates = fx.lookup(currency)
        aligned = pd.Series(1.0, index=sub.index)
        if not rates.empty:
            aligned = rates.reindex(sub["date"]).ffill()
        aligned = aligned.fillna(1.0 if currency == fx.base_currency else aligned.mean())
        factors.append(aligned)
    work["fx_rate"] = pd.concat(factors).sort_index()
    work[value_column] = work[value_column] * work["fx_rate"]
    work["currency_original"] = work[currency_column]
    work[currency_column] = fx.base_currency
    return work
