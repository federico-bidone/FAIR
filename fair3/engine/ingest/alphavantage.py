"""Fetcher per i tassi FX giornalieri forniti da Alpha Vantage."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
import requests

from .registry import BaseCSVFetcher

__all__ = ["AlphaVantageFXFetcher"]


DEFAULT_THROTTLE_SECONDS: Final[float] = 12.5


@dataclass(frozen=True)
class SymbolParts:
    """Rappresenta la coppia valutaria richiesta all'endpoint Alpha Vantage.

    Attributes:
        from_symbol: Valuta di partenza (tre lettere ISO).
        to_symbol: Valuta di destinazione (tre lettere ISO).
    """

    from_symbol: str
    to_symbol: str


class AlphaVantageFXFetcher(BaseCSVFetcher):
    """Scarica serie FX giornaliere da Alpha Vantage con throttling e guardie.

    Il fetcher richiede una chiave API fornita tramite il costruttore oppure
    tramite la variabile d'ambiente ``ALPHAVANTAGE_API_KEY``. Per rispettare i
    limiti del piano gratuito (massimo cinque richieste al minuto) viene
    applicato un intervallo minimo tra le chiamate.
    """

    SOURCE = "alphavantage_fx"
    LICENSE = "Alpha Vantage API — https://www.alphavantage.co/terms_of_service/"
    BASE_URL = "https://www.alphavantage.co/query"
    DEFAULT_SYMBOLS = ("USD", "GBP", "CHF")

    def __init__(
        self,
        *,
        api_key: str | None = None,
        throttle_seconds: float = DEFAULT_THROTTLE_SECONDS,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key or os.getenv("ALPHAVANTAGE_API_KEY")
        self._throttle_seconds = max(0.0, float(throttle_seconds))
        self._last_request_monotonic = 0.0

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Compone l'URL senza chiave API per preservare i log sanitizzati.

        Args:
            symbol: Codice valuta o coppia (es. ``USD`` oppure ``USD/EUR``).
            start: Data minima richiesta; l'endpoint Alpha Vantage non supporta
                filtri lato server e il parametro è gestito in post-processing.

        Returns:
            URL completo senza il parametro ``apikey``.

        Raises:
            ValueError: Se il simbolo non può essere interpretato come coppia FX.
        """

        parts = self._parse_symbol(symbol)
        query = urlencode(
            {
                "function": "FX_DAILY",
                "from_symbol": parts.from_symbol,
                "to_symbol": parts.to_symbol,
                "outputsize": "full",
                "datatype": "csv",
            }
        )
        return f"{self.BASE_URL}?{query}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il CSV Alpha Vantage nel formato FAIR canonico.

        Args:
            payload: Risposta testuale dell'endpoint.
            symbol: Simbolo richiesto dall'utente.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se il payload indica rate limit, chiave errata o HTML.
        """

        stripped = payload.lstrip()
        if stripped.startswith("<"):
            msg = "Alpha Vantage ha restituito HTML; controllare rate limit o endpoint."
            raise ValueError(msg)
        if stripped.startswith("{"):
            message = self._extract_json_error(stripped)
            raise ValueError(message)
        return self._simple_frame(
            payload,
            symbol,
            date_column="timestamp",
            value_column="close",
            rename={"close": "close"},
        )

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        """Scarica il payload applicando throttling e aggiungendo l'API key.

        Args:
            url: URL generato da :meth:`build_url` (senza chiave API).
            session: Sessione HTTP opzionale.

        Returns:
            Contenuto testuale della risposta.

        Raises:
            RuntimeError: Se la chiave API non è configurata.
        """

        if not self._api_key:
            msg = (
                "Alpha Vantage API key missing. Impostare ALPHAVANTAGE_API_KEY o "
                "passare api_key al costruttore."
            )
            raise RuntimeError(msg)
        self._respect_throttle()
        request_url = self._with_api_key(url)
        payload = super()._download(request_url, session=session)
        self._last_request_monotonic = time.monotonic()
        return payload

    def _respect_throttle(self) -> None:
        """Attende il tempo necessario per rispettare il rate limit dichiarato."""

        if self._throttle_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_monotonic
        remaining = self._throttle_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _with_api_key(self, url: str) -> str:
        """Aggiunge il parametro ``apikey`` all'URL senza loggare il valore."""

        parsed = urlparse(url)
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        key = self._api_key
        if key is None:  # pragma: no cover - garantito dal chiamante
            msg = "Alpha Vantage API key unexpectedly missing during URL rewrite."
            raise RuntimeError(msg)
        params["apikey"] = key
        new_query = urlencode(params)
        return urlunparse(parsed._replace(query=new_query))

    def _parse_symbol(self, symbol: str) -> SymbolParts:
        """Interpreta la stringa simbolo in coppia valutaria Alpha Vantage.

        Supporta formati ``AAA``, ``AAA/BBB`` e ``AAABBB``. In assenza della
        valuta di destinazione viene assunto ``EUR`` come richiesto dal progetto.
        """

        cleaned = symbol.strip().upper()
        if "/" in cleaned:
            base, quote = cleaned.split("/", maxsplit=1)
            base = base.strip()
            quote = quote.strip()
        elif len(cleaned) == 6:
            base, quote = cleaned[:3], cleaned[3:]
        elif len(cleaned) == 3:
            base, quote = cleaned, "EUR"
        else:
            msg = "Alpha Vantage symbol must be ISO currency (AAA) or pair (AAA/BBB)."
            raise ValueError(msg)
        if len(base) != 3 or len(quote) != 3:
            msg = "Currency codes must be three-letter ISO abbreviations."
            raise ValueError(msg)
        return SymbolParts(from_symbol=base, to_symbol=quote)

    def _extract_json_error(self, payload: str) -> str:
        """Restituisce un messaggio di errore leggibile da un payload JSON."""

        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:  # pragma: no cover - risposta inattesa
            return "Alpha Vantage ha restituito un payload JSON non riconosciuto."
        if "Note" in parsed:
            return "Alpha Vantage rate limit raggiunto; riprovare più tardi."
        if "Error Message" in parsed:
            return f"Alpha Vantage errore: {parsed['Error Message']}"
        if "Information" in parsed:
            return f"Alpha Vantage informazione: {parsed['Information']}"
        return "Alpha Vantage ha restituito un payload JSON non riconosciuto."
