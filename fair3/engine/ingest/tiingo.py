"""Fetcher per i prezzi azionari/ETF forniti via API Tiingo."""

from __future__ import annotations

import json
import os
import time
from typing import Final
from urllib.parse import urlencode

import pandas as pd
import requests

from .registry import BaseCSVFetcher

__all__ = ["TiingoFetcher"]


DEFAULT_THROTTLE_SECONDS: Final[float] = 1.0


class TiingoFetcher(BaseCSVFetcher):
    """Scarica serie daily da Tiingo rispettando il contratto di licenza.

    Il fetcher richiede una chiave API fornita dall'utente e inserita nella
    variabile ``TIINGO_API_KEY`` oppure passata direttamente al costruttore. La
    classe implementa throttling deterministico per rispettare i limiti
    contrattuali e normalizza il payload JSON nel formato canonico FAIR
    (colonne ``date``, ``value``, ``symbol``).
    """

    SOURCE = "tiingo"
    LICENSE = "Tiingo API — https://www.tiingo.com/documentation/general/terms-of-use"
    BASE_URL = "https://api.tiingo.com/tiingo/daily"
    DEFAULT_SYMBOLS = ("SPY", "VTI")
    HEADERS = {"User-Agent": "fair3-ingest/0.1", "Accept": "application/json"}

    def __init__(
        self,
        *,
        api_key: str | None = None,
        throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key or os.getenv("TIINGO_API_KEY")
        self._throttle_seconds = max(0.0, float(throttle_seconds))
        self._last_request_monotonic = 0.0

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Compone l'URL REST per il simbolo indicato.

        Args:
            symbol: Codice identificativo accettato da Tiingo (ticker o ISIN).
            start: Data minima richiesta; se presente viene passato come
                ``startDate`` all'endpoint.

        Returns:
            URL completo comprensivo dei parametri di query necessari.
        """

        clean_symbol = symbol.strip().upper()
        query: dict[str, str] = {"format": "json"}
        if start is not None:
            start_date = pd.Timestamp(start).date()
            query["startDate"] = start_date.isoformat()
        return f"{self.BASE_URL}/{clean_symbol}/prices?{urlencode(query)}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il payload JSON Tiingo in DataFrame canonico.

        Args:
            payload: Risposta testuale restituita dall'endpoint Tiingo.
            symbol: Simbolo originariamente richiesto.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol`` ordinate per
            data.

        Raises:
            ValueError: Se il payload è HTML, non è JSON valido o non contiene
                le colonne attese.
        """

        stripped = payload.lstrip()
        if stripped.startswith("<"):
            msg = "Tiingo ha restituito HTML inatteso; verificare endpoint o rate limit."
            raise ValueError(msg)
        try:
            parsed = json.loads(stripped or "[]")
        except json.JSONDecodeError as exc:  # pragma: no cover - caso limite
            msg = "Impossibile decodificare la risposta JSON di Tiingo."
            raise ValueError(msg) from exc
        if not isinstance(parsed, list):
            msg = "La risposta Tiingo deve essere una lista di osservazioni."
            raise ValueError(msg)
        if not parsed:
            return pd.DataFrame({"date": [], "value": [], "symbol": []})
        frame = pd.DataFrame(parsed)
        if "date" not in frame.columns:
            msg = "Colonna 'date' assente nella risposta Tiingo."
            raise ValueError(msg)
        value_column = "adjClose" if "adjClose" in frame.columns else "close"
        if value_column not in frame.columns:
            msg = "La risposta Tiingo non include 'adjClose' né 'close'."
            raise ValueError(msg)
        frame = frame[["date", value_column]].copy()
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        frame = frame.dropna(subset=["date"])
        frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
        frame = frame.dropna(subset=[value_column])
        frame = frame.assign(symbol=symbol.strip().upper(), value=frame[value_column])
        frame = frame.drop(columns=[value_column])
        frame["date"] = frame["date"].dt.tz_convert(None)
        frame = frame[["date", "value", "symbol"]]
        return frame

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        """Scarica il payload aggiungendo il token Tiingo e rispettando il throttle.

        Args:
            url: URL generato da :meth:`build_url`.
            session: Sessione HTTP riutilizzabile.

        Returns:
            Contenuto testuale della risposta Tiingo.

        Raises:
            RuntimeError: Se la chiave API non è configurata.
        """

        if not self._api_key:
            msg = "Tiingo API key missing. Impostare TIINGO_API_KEY o passare api_key al fetcher."
            raise RuntimeError(msg)
        self._respect_throttle()
        headers = dict(self.HEADERS)
        headers["Authorization"] = f"Token {self._api_key}"
        active_session = session or self.session
        close_session = False
        if active_session is None:
            active_session = requests.Session()
            close_session = True
        try:
            for attempt in range(1, self.RETRIES + 1):
                response = active_session.get(url, headers=headers, timeout=30)
                if response.ok:
                    response.encoding = response.encoding or "utf-8"
                    payload = response.text
                    self._last_request_monotonic = time.monotonic()
                    return payload
                if attempt == self.RETRIES:
                    response.raise_for_status()
                time.sleep(self.BACKOFF_SECONDS * attempt)
        finally:
            if close_session:
                active_session.close()
        raise RuntimeError(f"Unable to download from {url}")

    def _respect_throttle(self) -> None:
        """Applica un'attesa minima tra richieste successive."""

        if self._throttle_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self._throttle_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)
