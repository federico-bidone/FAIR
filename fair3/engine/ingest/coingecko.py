"""Fetcher CoinGecko per serie crypto normalizzate a 16:00 CET."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from urllib.parse import urlencode

import pandas as pd
import requests

from .registry import BaseCSVFetcher, IngestArtifact

__all__ = ["CoinGeckoFetcher"]


class CoinGeckoFetcher(BaseCSVFetcher):
    """Scarica prezzi crypto da CoinGecko e seleziona l'osservazione delle 16:00 CET.

    L'endpoint `market_chart/range` fornisce dati intraday; questo fetcher campiona
    un punto giornaliero allineato alle 16:00 CET (15:00 UTC), calcola un flag PIT
    quando il timestamp è sufficientemente vicino al target e conserva i prezzi in
    EUR come richiesto dalla pipeline FAIR.
    """

    SOURCE = "coingecko"
    LICENSE = "CoinGecko API — attribution required"
    BASE_URL = "https://api.coingecko.com/api/v3"
    DEFAULT_SYMBOLS = ("bitcoin", "ethereum")
    HEADERS = {
        "User-Agent": "fair3-ingest/0.2",
        "Accept": "application/json",
    }

    def __init__(
        self,
        *,
        vs_currency: str = "eur",
        delay_seconds: float = 1.0,
        now_fn: Callable[[], datetime] | None = None,
        **kwargs: object,
    ) -> None:
        """Inizializza il fetcher configurando valuta base, throttling e clock.

        Args:
            vs_currency: Valuta di quotazione richiesta dall'API CoinGecko.
            delay_seconds: Intervallo minimo tra le richieste per rispettare il
                limite gratuito (50 call/minuto → >= 1 secondo).
            now_fn: Funzione che restituisce l'orario corrente in UTC; utile nei
                test per ottenere URL deterministici.
            **kwargs: Parametri aggiuntivi inoltrati a :class:`BaseCSVFetcher`.
        """

        super().__init__(**kwargs)
        self.vs_currency = vs_currency.lower()
        self.delay_seconds = max(0.0, delay_seconds)
        self._now_fn = now_fn or (lambda: datetime.now(UTC))
        self._last_call_monotonic: float | None = None

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Compone l'URL `market_chart/range` per il simbolo richiesto.

        Args:
            symbol: Identificatore CoinGecko (es. ``bitcoin`` oppure ``ethereum``).
            start: Timestamp minimo fornito dal CLI (UTC naive o aware).

        Returns:
            URL completo con parametri ``vs_currency``, ``from`` e ``to``.
        """

        now = self._now_fn()
        end_ts = int(now.timestamp())
        if start is not None:
            if start.tzinfo is None:
                start_utc = start.tz_localize(UTC)
            else:
                start_utc = start.tz_convert(UTC)
            start_ts = int(start_utc.timestamp())
        else:
            default_start = now - pd.Timedelta(days=5 * 365)
            start_ts = int(default_start.timestamp())
        params = {
            "vs_currency": self.vs_currency,
            "from": str(start_ts),
            "to": str(end_ts),
        }
        query = urlencode(params)
        return f"{self.BASE_URL}/coins/{symbol}/market_chart/range?{query}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il payload JSON in DataFrame con osservazioni giornaliere.

        Args:
            payload: Risposta JSON restituita da CoinGecko.
            symbol: Identificatore richiesto dall'utente (ID coin).

        Returns:
            DataFrame con colonne ``date`` (UTC naive), ``value`` (float),
            ``symbol``, ``currency`` e ``pit_flag``.

        Raises:
            ValueError: Se il payload è HTML oppure non contiene la chiave
                ``prices``.
        """

        text = payload.strip()
        if text.startswith("<"):
            msg = "CoinGecko payload appears to be HTML"
            raise ValueError(msg)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - difensivo
            msg = "Unable to decode CoinGecko JSON payload"
            raise ValueError(msg) from exc
        if isinstance(data, dict) and "error" in data:
            msg = f"CoinGecko error: {data['error']}"
            raise ValueError(msg)
        if not isinstance(data, dict) or "prices" not in data:
            msg = "CoinGecko payload missing 'prices' key"
            raise ValueError(msg)
        prices = data["prices"]
        if not prices:
            return pd.DataFrame(columns=["date", "value", "symbol", "currency", "pit_flag"])
        frame = pd.DataFrame(prices, columns=["timestamp_ms", "price"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
        frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
        frame = frame.dropna(subset=["timestamp", "price"]).reset_index(drop=True)
        if frame.empty:
            return pd.DataFrame(columns=["date", "value", "symbol", "currency", "pit_flag"])
        frame["date_floor"] = frame["timestamp"].dt.floor("D")
        frame["target"] = frame["date_floor"] + pd.Timedelta(hours=15)
        frame["delta"] = (frame["timestamp"] - frame["target"]).abs()
        idx = frame.groupby("date_floor")["delta"].idxmin()
        sampled = frame.loc[idx.values].copy().reset_index(drop=True)
        sampled["pit_flag"] = (sampled["delta"] <= pd.Timedelta(minutes=15)).astype("int8")
        sampled["date"] = sampled["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None)
        result = pd.DataFrame(
            {
                "date": sampled["date"],
                "value": sampled["price"],
                "symbol": symbol,
                "currency": self.vs_currency.upper(),
                "pit_flag": sampled["pit_flag"],
            }
        )
        return result.sort_values("date").reset_index(drop=True)

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        """Scarica il payload rispettando il throttling configurato."""

        if self.delay_seconds > 0:
            now = time.monotonic()
            if self._last_call_monotonic is not None:
                elapsed = now - self._last_call_monotonic
                remaining = self.delay_seconds - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            self._last_call_monotonic = time.monotonic()
        return super()._download(url, session=session)

    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: datetime | pd.Timestamp | None = None,
        as_of: datetime | None = None,
        progress: bool = False,
        session: requests.Session | None = None,
    ) -> IngestArtifact:
        """Esegue l'ingest ereditando la logica base senza modifiche."""

        return super().fetch(
            symbols=symbols,
            start=start,
            as_of=as_of,
            progress=progress,
            session=session,
        )
