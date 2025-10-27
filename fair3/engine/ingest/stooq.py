"""Fetcher Stooq per prezzi giornalieri end-of-day."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from urllib.parse import parse_qs, urlparse

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["StooqFetcher"]

_STOOQ_TZ: Final[str] = "Europe/Warsaw"


class StooqFetcher(BaseCSVFetcher):
    """Scarica e normalizza i CSV giornalieri pubblicati da Stooq."""

    SOURCE = "stooq"
    LICENSE = "Stooq.com data usage policy"
    BASE_URL = "https://stooq.com/q/d/l/"
    DEFAULT_SYMBOLS = ("spx",)

    def __init__(
        self,
        *,
        payload_cache: Mapping[str, str] | None = None,
        **kwargs: object,
    ) -> None:
        """Inizializza il fetcher opzionalmente con un cache di payload già scaricati.

        Args:
            payload_cache: Mappa facoltativa ``symbol → payload`` riutilizzabile per
                evitare download ripetuti nello stesso processo.
            **kwargs: Argomenti propagati a :class:`BaseCSVFetcher` (es. ``raw_root``).
        """

        super().__init__(**kwargs)
        self._payload_cache: dict[str, str] = {}
        if payload_cache:
            for symbol, payload in payload_cache.items():
                key = self._canonical_symbol(symbol)
                self._payload_cache[key] = payload

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce l'URL CSV per il simbolo richiesto.

        Args:
            symbol: Identificatore richiesto (case insensitive, supporta suffissi
                ``.us``/``.pl``).
            start: Data minima desiderata (non supportata dall'endpoint Stooq).

        Returns:
            URL completo con parametri ``s=<symbol>&i=d``.
        """

        ticker = self._canonical_symbol(symbol)
        params: list[str] = [f"s={ticker}", "i=d"]
        return f"{self.BASE_URL}?{'&'.join(params)}"

    def parse(self, payload: str | bytes, symbol: str) -> pd.DataFrame:
        """Normalizza il CSV Stooq gestendo caching e fuso orario originale.

        Args:
            payload: CSV (stringa o bytes) restituito dall'endpoint Stooq.
            symbol: Simbolo richiesto (verrà normalizzato in upper-case per l'output).

        Returns:
            DataFrame con colonne ``date``, ``value``, ``symbol`` e ``tz``.

        Raises:
            ValueError: Se il payload appare come HTML (tipico di rate limit o
                simboli inesistenti) oppure se mancano le colonne attese.
        """

        text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else payload
        if text.lstrip().startswith("<"):
            msg = "Stooq: payload HTML (ticker inesistente o endpoint non CSV)"
            raise ValueError(msg)
        lines = text.splitlines()
        if lines:
            header_parts = [part.strip() for part in lines[0].split(",")]
            lines[0] = ",".join(header_parts)
            text = "\n".join(lines)
        frame = self._simple_frame(
            text,
            self._output_symbol(symbol),
            date_column="Date",
            value_column="Close",
        )
        frame["value"] = frame["value"].astype(float)
        frame["tz"] = _STOOQ_TZ
        return frame

    # ------------------------------------------------------------------
    def _download(
        self,
        url: str,
        *,
        session: object | None = None,
    ) -> str:
        """Scarica il payload riutilizzando il cache in memoria quando possibile."""

        symbol = self._extract_symbol_from_url(url)
        cache_key = self._canonical_symbol(symbol) if symbol is not None else None
        if cache_key is not None and cache_key in self._payload_cache:
            return self._payload_cache[cache_key]
        text = super()._download(url, session=session)
        if cache_key is not None:
            self._payload_cache[cache_key] = text
        return text

    def _canonical_symbol(self, symbol: str) -> str:
        """Restituisce il simbolo normalizzato in lower-case."""

        normalized = symbol.strip().lower()
        if not normalized:
            msg = "Stooq: symbol must be non-empty"
            raise ValueError(msg)
        return normalized

    def _output_symbol(self, symbol: str) -> str:
        """Restituisce il simbolo in upper-case per il DataFrame finale."""

        return self._canonical_symbol(symbol).upper()

    def _extract_symbol_from_url(self, url: str) -> str | None:
        """Estrae il parametro ``s`` dall'URL generato per il download."""

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        raw = query.get("s")
        if not raw:
            return None
        return raw[0]
