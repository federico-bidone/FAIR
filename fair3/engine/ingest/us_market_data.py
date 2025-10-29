"""Fetcher manuale per il repository SteelCerberus/us-market-data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .registry import BaseCSVFetcher


@dataclass(frozen=True)
class OutputMapping:
    """Descrive la corrispondenza tra colonne interne e simboli esposti.

    Attributes:
        symbol: Nome del simbolo esposto dal fetcher (es. ``sp500_price``).
        column: Nome della colonna interna contenente i valori richiesti.
    """

    symbol: str
    column: str


DEFAULT_OUTPUTS: tuple[OutputMapping, ...] = (
    OutputMapping(symbol="sp500_price", column="close"),
    OutputMapping(symbol="sp500_total_return", column="total_return"),
    OutputMapping(symbol="sp500_dividend", column="dividend"),
    OutputMapping(symbol="sp500_return", column="daily_return"),
)


def import_us_market_data_local(root: Path | str) -> pd.DataFrame:
    """Importa i CSV locali del progetto us-market-data componendo una serie unica.

    Args:
        root: Directory che contiene i file CSV clonati dal repository
            ``SteelCerberus/us-market-data``.

    Returns:
        DataFrame con colonne ``date`` (``datetime64[ns]``), ``close``,
        ``total_return``, ``dividend`` e ``daily_return``. Le colonne numeriche sono
        espresse in termini decimali e possono contenere ``NaN`` laddove la fonte
        non fornisce il dato.

    Raises:
        FileNotFoundError: Se la directory non esiste o non contiene alcun CSV.
        ValueError: Se i CSV non espongono la colonna ``Date`` oppure nessuna delle
            colonne necessarie per costruire il total return.
    """

    root_path = Path(root)
    if not root_path.exists():
        msg = (
            "Manual repository missing. Clone SteelCerberus/us-market-data and "
            f"copy CSV files under {root_path}."
        )
        raise FileNotFoundError(msg)
    csv_files = sorted(root_path.glob("**/*.csv"))
    if not csv_files:
        msg = f"No CSV files found under {root_path}; ensure manual data is present."
        raise FileNotFoundError(msg)

    frames: list[pd.DataFrame] = []
    for csv_path in csv_files:
        frame = pd.read_csv(csv_path)
        normalized = _normalize_columns(frame)
        if "date" not in normalized.columns:
            msg = f"us-market-data CSV missing 'Date' column; file={csv_path.name}"
            raise ValueError(msg)
        normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
        frames.append(normalized)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["date"]).sort_values("date")
    combined = combined.groupby("date", as_index=False).last()

    numeric_columns = {}
    for name in [
        "close",
        "adjusted_close",
        "return",
        "dividend",
        "daily_dividend",
        "accumulated_dividend",
    ]:
        source = combined.get(name)
        if source is None:
            numeric = pd.Series(np.nan, index=combined.index, dtype="float64")
        else:
            numeric = pd.to_numeric(source, errors="coerce")
        numeric_columns[name] = numeric
    close = numeric_columns["close"]
    adjusted_close = numeric_columns["adjusted_close"]
    raw_return = numeric_columns["return"]
    dividend_daily = numeric_columns["daily_dividend"]
    dividend_lump = numeric_columns["dividend"]
    accumulated_dividend = numeric_columns["accumulated_dividend"]

    if adjusted_close.notna().any():
        total_return = adjusted_close
    elif close.notna().any() and accumulated_dividend.notna().any():
        total_return = close + accumulated_dividend.fillna(0.0)
    else:
        msg = (
            "Unable to compute total return: expected 'Adjusted Close' or both "
            "'Close' and 'Accumulated Dividend' columns."
        )
        raise ValueError(msg)

    if raw_return.notna().any():
        daily_return = raw_return
    else:
        daily_return = total_return.pct_change()

    if dividend_daily.notna().any():
        dividend = dividend_daily
    else:
        dividend = dividend_lump

    result = pd.DataFrame(
        {
            "date": combined["date"],
            "close": close,
            "total_return": total_return,
            "dividend": dividend,
            "daily_return": daily_return,
        }
    )
    return result


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalizza le intestazioni rendendole minuscole con underscore.

    Args:
        frame: DataFrame originale letto da CSV.

    Returns:
        DataFrame con colonne rinominate in minuscolo e underscore.
    """

    mapping = {column: column.strip().lower().replace(" ", "_") for column in frame.columns}
    return frame.rename(columns=mapping)


class USMarketDataFetcher(BaseCSVFetcher):
    """Fetcher per dati storici S&P 500 dal repository us-market-data.

    Attributes:
        manual_root: Directory locale che ospita i CSV scaricati manualmente.
    """

    SOURCE = "usmarket"
    LICENSE = "SteelCerberus us-market-data — academic/educational use"
    BASE_URL = "https://github.com/SteelCerberus/us-market-data"
    DEFAULT_SYMBOLS = tuple(mapping.symbol for mapping in DEFAULT_OUTPUTS)

    def __init__(
        self,
        *,
        manual_root: Path | str | None = None,
        raw_root: Path | str | None = None,
        outputs: Iterable[OutputMapping] | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(raw_root=raw_root, **kwargs)
        self.manual_root = (
            Path(manual_root) if manual_root is not None else Path("data") / "us_market_data"
        )
        self._dataset: pd.DataFrame | None = None
        if outputs is None:
            self._outputs = tuple(DEFAULT_OUTPUTS)
        else:
            self._outputs = tuple(outputs)

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce il percorso manuale usato come origine dei CSV locali.

        Args:
            symbol: Simbolo richiesto (ignorato; incluso per compatibilità).
            start: Timestamp minimo richiesto (ignorato per dataset manuali).

        Returns:
            Stringa ``manual://`` che rappresenta la directory manuale.

        Raises:
            FileNotFoundError: Se la directory manuale non esiste.
        """

        if not self.manual_root.exists():
            msg = (
                "Manual directory missing; clone SteelCerberus/us-market-data "
                f"under {self.manual_root}."
            )
            raise FileNotFoundError(msg)
        return f"manual://{self.manual_root}"  # pragma: no cover - deterministic string

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Restituisce il DataFrame normalizzato per il simbolo richiesto.

        Args:
            payload: Stringa ritornata da ``_download`` (ignorata).
            symbol: Codice della serie richiesta (es. ``sp500_total_return``).

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.
        """

        dataset = self._load_dataset()
        column = self._resolve_column(symbol)
        frame = pd.DataFrame(
            {
                "date": dataset["date"],
                "value": pd.to_numeric(dataset[column], errors="coerce"),
                "symbol": symbol,
            }
        )
        frame = frame.dropna(subset=["date", "value"]).reset_index(drop=True)
        return frame

    def _download(self, url: str, *, session: object | None = None) -> str:
        """Sovrascrive il download evitando letture ripetute dei file manuali.

        Args:
            url: Percorso manuale generato da ``build_url``.
            session: Sessione HTTP opzionale (ignorata in questo contesto).

        Returns:
            Stringa ``manual://`` da passare al parser.
        """

        self._load_dataset()
        return url

    def _load_dataset(self) -> pd.DataFrame:
        """Carica e cache in memoria il DataFrame aggregato dei CSV manuali.

        Returns:
            DataFrame aggregato prodotto da ``import_us_market_data_local``.
        """

        if self._dataset is None:
            self._dataset = import_us_market_data_local(self.manual_root)
        return self._dataset

    def _resolve_column(self, symbol: str) -> str:
        """Mappa il simbolo richiesto nella colonna interna corrispondente.

        Args:
            symbol: Nome del simbolo richiesto dal fetcher.

        Returns:
            Nome della colonna interna da utilizzare per il simbolo.

        Raises:
            ValueError: Se il simbolo non è supportato.
        """

        lookup: Mapping[str, str] = {entry.symbol: entry.column for entry in self._outputs}
        try:
            return lookup[symbol]
        except KeyError as exc:
            msg = f"Unsupported us-market-data symbol '{symbol}'"
            raise ValueError(msg) from exc
