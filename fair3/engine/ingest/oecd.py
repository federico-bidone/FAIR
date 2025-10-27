from __future__ import annotations

from collections.abc import Iterable
from io import StringIO
from urllib.parse import parse_qsl, urlencode

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["OECDFetcher"]


class OECDFetcher(BaseCSVFetcher):
    """Scarica serie macro OECD via SDMX JSON/CSV normalizzandole nel formato FAIR."""

    SOURCE = "oecd"
    LICENSE = "OECD Terms and Conditions"
    BASE_URL = "https://stats.oecd.org/sdmx-json/data"
    DEFAULT_SYMBOLS = (
        "MEI_CLI/LOLITOAA.IT.A",
        "MEI_CLI/LOLITOAA.EA19.A",
    )

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Compone l'URL SDMX per una serie OECD.

        Args:
            symbol: Percorso SDMX nel formato ``<dataset>/<dimensioni>`` con
                eventuali query string aggiuntive (es. ``MEI_CLI/LOLITOAA.IT.A``).
            start: Data minima (UTC) da cui richiedere le osservazioni; se
                fornita viene passata a ``startTime``.

        Returns:
            URL completo con parametri standardizzati (CSV, dimensione tempo).

        Raises:
            ValueError: Se il percorso del simbolo risulta vuoto.
        """
        path, _, extra_query = symbol.partition("?")
        dataset_path = path.strip("/")
        if not dataset_path:
            msg = "OECD symbol must include dataset and series path"
            raise ValueError(msg)
        params: dict[str, str] = {
            "contentType": "csv",
            "detail": "code",
            "dimensionAtObservation": "TimeDimension",
            "timeOrder": "Ascending",
        }
        if start is not None:
            params["startTime"] = start.strftime("%Y-%m-%d")
        if extra_query:
            for key, value in parse_qsl(extra_query, keep_blank_values=True):
                params[key] = value
        query = urlencode(params)
        return f"{self.BASE_URL}/{dataset_path}?{query}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il CSV OECD in DataFrame con colonne canoniche.

        Args:
            payload: Contenuto CSV ritornato dall'API.
            symbol: Simbolo originale richiesto.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se il payload sembra HTML o non espone colonne temporali
                e di valore riconosciute.
        """
        if payload.lstrip().startswith("<"):
            msg = "OECD: payload HTML (rate limit o errore)"
            raise ValueError(msg)
        frame = pd.read_csv(StringIO(payload))
        if frame.empty:
            return pd.DataFrame(columns=["date", "value", "symbol"])
        normalised = self._normalise_columns(frame.columns)
        frame = frame.rename(columns=normalised)
        date_column = self._pick_first(frame.columns, ("TIME_PERIOD", "TIME", "DATE"))
        if date_column is None:
            msg = "OECD: missing TIME_PERIOD/TIME/DATE column"
            raise ValueError(msg)
        value_column = self._pick_first(frame.columns, ("OBS_VALUE", "VALUE"))
        if value_column is None:
            msg = "OECD: missing OBS_VALUE/VALUE column"
            raise ValueError(msg)
        tidy = pd.DataFrame(
            {
                "date": pd.to_datetime(frame[date_column], errors="coerce"),
                "value": pd.to_numeric(frame[value_column], errors="coerce"),
                "symbol": symbol,
            }
        )
        tidy = tidy.dropna(subset=["date", "value"]).reset_index(drop=True)
        return tidy

    def _normalise_columns(self, columns: Iterable[str]) -> dict[str, str]:
        """Converte header arbitrari in slug maiuscoli senza spazi.

        Args:
            columns: Header originali del CSV.

        Returns:
            Mapping ``originale -> normalizzato`` adatto a ``DataFrame.rename``.
        """
        return {name: name.strip().upper().replace(" ", "_") for name in columns}

    def _pick_first(self, available: Iterable[str], candidates: Iterable[str]) -> str | None:
        """Restituisce il primo candidato presente fra le colonne disponibili.

        Args:
            available: Collezione di nomi di colonna disponibili nel DataFrame.
            candidates: Elenco ordinato di colonne da cercare in ordine di
                preferenza.

        Returns:
            Il nome originale della colonna candidata se presente, altrimenti
            ``None``.
        """

        available_upper = {name.upper(): name for name in available}
        for candidate in candidates:
            key = candidate.upper()
            if key in available_upper:
                return available_upper[key]
        return None
