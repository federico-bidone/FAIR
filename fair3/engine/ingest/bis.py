from __future__ import annotations

from collections.abc import Iterable
from io import StringIO

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["BISFetcher"]


class BISFetcher(BaseCSVFetcher):
    """Scarica serie REER/NEER della BIS via SDMX e le normalizza."""

    SOURCE = "bis"
    LICENSE = "Bank for International Settlements (BIS) Terms of Use"
    BASE_URL = "https://stats.bis.org/api/v1/data"
    DEFAULT_SYMBOLS = ("REER:USA:M", "NEER:USA:M")

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Compone l'URL SDMX completo per una serie BIS specifica.

        Args:
            symbol: Stringa formattata come ``<dataset>:<area>:<freq>`` (es. ``REER:ITA:M``).
            start: Data minima da cui iniziare la serie; arrotondata alla frequenza BIS.

        Returns:
            URL completo verso l'endpoint SDMX BIS.

        Raises:
            ValueError: Se il simbolo non rispetta il formato atteso o la frequenza
            non è supportata.
        """
        dataset, area, frequency = self._parse_symbol(symbol)
        path = f"{dataset}/{frequency}.{area}"
        params: list[str] = ["detail=dataonly", "format=csv"]
        if start is not None:
            params.append(f"startPeriod={self._format_start(start, frequency)}")
        query = "&".join(params)
        return f"{self.BASE_URL}/{path}?{query}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Normalizza il CSV BIS in un DataFrame (date, value, symbol).

        Args:
            payload: Contenuto CSV restituito dall'endpoint SDMX.
            symbol: Identificatore della serie richiesto.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se il payload risulta HTML o non contiene le colonne attese.
        """
        if payload.lstrip().startswith("<"):
            msg = "BIS: payload HTML (rate limit o endpoint non CSV)"
            raise ValueError(msg)
        csv = pd.read_csv(StringIO(payload))
        if csv.empty:
            return pd.DataFrame(columns=["date", "value", "symbol"])
        csv = csv.rename(columns=self._normalize_columns(csv.columns))
        if "TIME_PERIOD" not in csv.columns or "OBS_VALUE" not in csv.columns:
            msg = "BIS: expected TIME_PERIOD/OBS_VALUE columns in payload"
            raise ValueError(msg)
        _, _, frequency = self._parse_symbol(symbol)
        date_series = self._coerce_dates(csv["TIME_PERIOD"], frequency)
        frame = pd.DataFrame(
            {
                "date": date_series,
                "value": pd.to_numeric(csv["OBS_VALUE"], errors="coerce"),
                "symbol": symbol,
            }
        )
        frame = frame.dropna(subset=["date", "value"]).reset_index(drop=True)
        frame["value"] = frame["value"].astype(float)
        return frame

    def _parse_symbol(self, symbol: str) -> tuple[str, str, str]:
        """Scompone il simbolo BIS e valida dataset, area e frequenza.

        Args:
            symbol: Stringa ``<dataset>:<area>:<freq>``.

        Returns:
            Tuple con dataset (es. ``REER``), area (ISO-3) e frequenza (``M``, ``Q`` o ``A``).

        Raises:
            ValueError: Se la stringa non ha esattamente tre componenti o
            area/frequenza non sono validi.
        """
        parts = [part.strip().upper() for part in symbol.split(":")]
        if len(parts) != 3:
            msg = "BIS symbol must follow <dataset>:<area>:<freq>"
            raise ValueError(msg)
        dataset, area, frequency = parts
        if len(area) != 3:
            msg = "BIS area must be a 3-letter ISO code"
            raise ValueError(msg)
        if frequency not in {"M", "Q", "A"}:
            msg = "BIS frequency must be one of {'M', 'Q', 'A'}"
            raise ValueError(msg)
        return dataset, area, frequency

    def _format_start(self, start: pd.Timestamp, frequency: str) -> str:
        """Converte la data di start nel formato richiesto dalla frequenza BIS.

        Args:
            start: Timestamp minimo indicato dall'utente.
            frequency: Codice di frequenza BIS (``M``, ``Q`` o ``A``).

        Returns:
            Stringa pronta per il parametro ``startPeriod``.
        """
        if frequency == "M":
            return start.to_period("M").strftime("%Y-%m")
        if frequency == "Q":
            return start.to_period("Q").strftime("%Y-Q%q")
        if frequency == "A":
            return f"{start.year}"
        msg = "Unsupported BIS frequency"
        raise ValueError(msg)

    def _normalize_columns(self, columns: Iterable[str]) -> dict[str, str]:
        """Uniforma header CSV rimuovendo spazi e forzando maiuscole.

        Args:
            columns: Lista originale delle colonne del CSV.

        Returns:
            Mapping `originale -> normalizzato` da usare con ``DataFrame.rename``.
        """
        return {name: name.strip().upper().replace(" ", "_") for name in columns}

    def _coerce_dates(self, values: pd.Series, frequency: str) -> pd.Series:
        """Converte la colonna `TIME_PERIOD` nella frequenza richiesta.

        Args:
            values: Serie originale del CSV con i periodi.
            frequency: Codice di frequenza BIS (``M``, ``Q`` o ``A``).

        Returns:
            Serie pandas con timestamp coerenti, usando l'inizio del periodo.
        """
        cleaned = values.astype(str).str.strip()
        if frequency == "M":
            return pd.to_datetime(cleaned, format="%Y-%m", errors="coerce")
        if frequency == "Q":
            try:
                periods = pd.PeriodIndex(cleaned, freq="Q")
                return periods.to_timestamp(how="start")
            except (ValueError, TypeError):
                return pd.to_datetime(cleaned, errors="coerce")
        if frequency == "A":
            return pd.to_datetime(cleaned, format="%Y", errors="coerce")
        return pd.to_datetime(cleaned, errors="coerce")
