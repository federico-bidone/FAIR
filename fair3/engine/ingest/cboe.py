"""Fetcher CBOE per serie VIX e SKEW normalizzate nello schema FAIR."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["CBOEFetcher"]


class CBOEFetcher(BaseCSVFetcher):
    """Scarica serie CBOE (VIX, SKEW) e le normalizza in formato FAIR."""

    SOURCE = "cboe"
    LICENSE = "Cboe Exchange, Inc. data subject to terms"
    BASE_URL = "https://cdn.cboe.com/api/global/us_indices/daily_prices"
    DEFAULT_SYMBOLS = ("VIX", "SKEW")

    _DATASETS: dict[str, dict[str, Any]] = {
        "VIX": {
            "file": "VIX_History.csv",
            "rename": {
                "DATE": "date",
                "Date": "date",
                "Close": "close",
                "CLOSE": "close",
                "VIX Close": "close",
            },
            "value_column": "close",
        },
        "SKEW": {
            "file": "SKEW_History.csv",
            "rename": {
                "DATE": "date",
                "Date": "date",
                "SKEW": "skew",
                "Skew": "skew",
            },
            "value_column": "skew",
        },
    }

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce l'URL pubblico per il simbolo richiesto.

        Args:
            symbol: Codice della serie (VIX o SKEW) indipendente dal case.
            start: Timestamp minimo richiesto dal chiamante; la sorgente non
                supporta filtri server-side e quindi il valore viene ignorato.

        Returns:
            URL completo da cui scaricare il CSV.

        Raises:
            ValueError: Se il simbolo richiesto non è supportato.
        """

        del start  # Parametro non supportato dalla sorgente ma richiesto dall'interfaccia.
        symbol_key = symbol.upper()
        if symbol_key not in self._DATASETS:
            msg = f"Unsupported CBOE symbol: {symbol}"
            raise ValueError(msg)
        file_name = self._DATASETS[symbol_key]["file"]
        return f"{self.BASE_URL}/{file_name}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il CSV CBOE in DataFrame canonico.

        Args:
            payload: Contenuto CSV restituito dall'endpoint CBOE.
            symbol: Simbolo richiesto originariamente dal chiamante.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se il payload appare HTML (tipico di errori/ratelimit) o
                se le colonne attese non sono presenti.
        """

        text = payload.lstrip()
        if text.startswith("<"):
            raise ValueError(
                "CBOE payload appears to be HTML; request likely rate-limited or invalid."
            )

        symbol_key = symbol.upper()
        if symbol_key not in self._DATASETS:
            msg = f"Unsupported CBOE symbol: {symbol}"
            raise ValueError(msg)

        dataset = self._DATASETS[symbol_key]
        rename: dict[str, str] = dataset["rename"]
        csv = pd.read_csv(StringIO(payload))
        if rename:
            csv = csv.rename(columns={col: rename.get(col, col) for col in csv.columns})

        date_column = "date"
        value_column = dataset["value_column"]
        if date_column not in csv.columns or value_column not in csv.columns:
            msg = (
                "Expected columns "
                f"'{date_column}' and '{value_column}' in CBOE payload for {symbol_key}."
            )
            raise ValueError(msg)

        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(csv[date_column], errors="coerce"),
                "value": pd.to_numeric(csv[value_column], errors="coerce"),
                "symbol": symbol_key,
            }
        )
        frame = frame.dropna(subset=["date", "value"]).reset_index(drop=True)
        return frame
