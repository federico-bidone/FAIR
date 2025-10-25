from __future__ import annotations

"""Gestione dei tassi FX per normalizzare i prezzi nel pannello TR."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from fair3.engine.utils.io import ensure_dir

__all__ = ["FXFrame", "load_fx_rates", "convert_to_base"]


@dataclass(slots=True)
class FXFrame:
    """Contenitore delle curve FX rispetto alla valuta base.

    Conserviamo le serie in un `DataFrame` indicizzato per data così da
    facilitare merge e persistenza; i nomi colonna seguono il formato
    `<currency>_to_<base>`.
    """

    base_currency: str
    rates: pd.DataFrame

    def lookup(self, currency: str) -> pd.Series:
        """Restituisce la serie FX per la valuta richiesta.

        Se la valuta coincide con la base ritorniamo una serie costante di 1.0
        per evitare moltiplicazioni inutili a valle.
        """
        if currency == self.base_currency:
            return pd.Series(1.0, index=self.rates.index)
        column = f"{currency}_to_{self.base_currency}"
        if column not in self.rates.columns:
            raise KeyError(f"missing FX column {column}")
        return self.rates[column]

    def save(self, path: Path) -> Path:
        """Salva le curve FX in CSV ordinato cronologicamente."""

        ensure_dir(path.parent)
        frame = self.rates.copy()
        frame.index = frame.index.strftime("%Y-%m-%d")
        frame.to_csv(path)
        return path


def load_fx_rates(records: Iterable[pd.DataFrame], base_currency: str) -> FXFrame:
    """Costruisce la tabella FX a partire dai record raw dell'ingest.

    I record sono `DataFrame` uniformi con colonne `date`, `value`, `symbol`;
    convertiamo `value` in colonne canoniche `USD_to_EUR`, ecc., normalizziamo
    le date e applichiamo un merge outer per non perdere osservazioni sparse.
    """

    frames: list[pd.DataFrame] = []
    for record in records:
        if {"date", "value", "symbol"} - set(record.columns):
            msg = "il record deve contenere le colonne date/value/symbol"
            raise ValueError(msg)
        symbol = record["symbol"].iat[0]
        invert = False
        if "/" in symbol:
            base, quote = symbol.split("/", 1)
            # Normalizziamo i simboli FX in formato `<quote>_to_<base>` per
            # allinearli all'interfaccia `FXFrame.lookup`.
            symbol = f"{quote}_to_{base}"
            invert = True
        frame = record.copy()
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        if invert:
            if (frame["value"] == 0).any():
                msg = (
                    "impossibile invertire il tasso FX normalizzato "
                    f"{symbol}: contiene uno zero"
                )
                raise ValueError(msg)
            frame["value"] = 1 / frame["value"]
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
    """Converte la colonna dei prezzi nella valuta base dell'oggetto FX.

    Le colonne richieste vengono validate in anticipo per ottenere errori
    esplicativi; per ogni valuta applichiamo un forward fill delle serie FX e,
    in mancanza di dati, ripieghiamo su 1.0 (valuta base) o sulla media
    osservata così da segnalare chiaramente eventuali lacune.
    """

    if frame.empty:
        return frame
    required = {"date", currency_column, value_column}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"colonne mancanti nel frame: {missing}")

    work = frame.copy()
    work["date"] = pd.to_datetime(work["date"]).dt.normalize()
    work = work.sort_values(["symbol", "date"])  # type: ignore[arg-type]
    factors = []
    for currency, sub in work.groupby(currency_column):
        # Ogni valuta è processata separatamente così da usare la serie FX
        # corretta e mantenere la tracciabilità nella QA finale.
        rates = fx.lookup(currency)
        if not rates.empty:
            reindexed = rates.reindex(sub["date"]).ffill()
            if currency == fx.base_currency:
                reindexed = reindexed.fillna(1.0)
            else:
                fallback = reindexed.dropna().mean()
                if pd.isna(fallback):
                    fallback = 1.0
                reindexed = reindexed.fillna(fallback)
            aligned = pd.Series(reindexed.to_numpy(), index=sub.index, dtype=float)
        else:
            default = 1.0
            aligned = pd.Series(default, index=sub.index, dtype=float)
        factors.append(aligned)
    work["fx_rate"] = pd.concat(factors).sort_index()
    work[value_column] = work[value_column] * work["fx_rate"]
    work["currency_original"] = work[currency_column]
    work[currency_column] = fx.base_currency
    return work
