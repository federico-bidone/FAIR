"""Fetcher Yahoo Finance come fallback opzionale basato su ``yfinance``.

Il modulo fornisce un fetcher compatibile con :class:`BaseCSVFetcher` che
utilizza ``yfinance`` per scaricare serie daily rettificate. Poiché l'API non
è ufficiale e prevede limiti sul riutilizzo, l'implementazione impone una
finestra massima di cinque anni, applica un ritardo configurabile tra le
richieste e logga esplicitamente la licenza "personal/non-commercial use".
Quando ``yfinance`` non è installato l'utente riceve un errore
esplicativo con i passi per installare la dipendenza opzionale.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import Final
from urllib.parse import parse_qs, urlencode, urlparse

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["YahooFetcher"]

_MAX_LOOKBACK_YEARS: Final[int] = 5


@dataclass(slots=True)
class _YahooRequest:
    """Rappresenta i parametri estratti dalla pseudo URL ``yfinance://``."""

    symbol: str
    start: pd.Timestamp | None


class YahooFetcher(BaseCSVFetcher):
    """Scarica prezzi daily da Yahoo Finance tramite la libreria ``yfinance``.

    L'endpoint ufficiale non è documentato, pertanto il fetcher applica un
    approccio conservativo: limita l'intervallo a cinque anni antecedenti la
    data corrente, impone un ritardo di default di due secondi fra le
    richieste e restituisce serie auto-aggiustate (dividendi/split) usando la
    colonna *Close* di ``yfinance``.

    Attributes:
      SOURCE: Codice sorgente per il registry ingest ("yahoo").
      LICENSE: Nota riassuntiva dei termini di utilizzo.
      BASE_URL: Schema fittizio utilizzato per propagare parametri all'helper
        di download.
      DEFAULT_SYMBOLS: Lista ridotta di simboli di default (``("SPY",)``) per
        CLI e test interattivi.
    """

    SOURCE = "yahoo"
    LICENSE = "Yahoo! Finance Terms of Service — personal/non-commercial use"
    BASE_URL = "yfinance://"
    DEFAULT_SYMBOLS = ("SPY",)

    def __init__(self, *, delay_seconds: float = 2.0, **kwargs: object) -> None:
        """Inizializza il fetcher opzionalmente disattivando il ritardo.

        Args:
          delay_seconds: Numero di secondi da attendere tra due richieste
            consecutive. Impostare a ``0`` nei test per evitare rallentamenti.
          **kwargs: Parametri inoltrati al costruttore della superclasse
            (:class:`BaseCSVFetcher`).
        """

        super().__init__(**kwargs)
        self._delay_seconds = max(delay_seconds, 0.0)

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Costruisce la pseudo URL ``yfinance://`` per un simbolo richiesto.

        Args:
          symbol: Ticker Yahoo Finance (case insensitive).
          start: Data minima desiderata. Verrà tagliata a cinque anni fa.

        Returns:
          Stringa con schema ``yfinance://<SYMBOL>?start=<ISO8601>``.
        """

        ticker = self._normalise_symbol(symbol)
        params: dict[str, str] = {}
        if start is not None:
            params["start"] = pd.to_datetime(start, utc=True).isoformat()
        query = f"?{urlencode(params)}" if params else ""
        return f"{self.BASE_URL}{ticker}{query}"

    def parse(self, payload: str | bytes, symbol: str) -> pd.DataFrame:
        """Converte il CSV auto-generato in DataFrame canonico.

        Args:
          payload: Stringa CSV generata da :meth:`_download`.
          symbol: Simbolo richiesto (usato per popolare la colonna finale).

        Returns:
          DataFrame con colonne ``date``, ``value``, ``symbol``.

        Raises:
          ValueError: Se le colonne ``date``/``value`` non sono presenti.
        """

        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
        return self._simple_frame(
            text,
            self._normalise_symbol(symbol),
            date_column="date",
            value_column="value",
        )

    def _download(self, url: str, *, session: object | None = None) -> str:
        """Scarica i dati tramite ``yfinance`` rispettando finestre e ritardi.

        Args:
          url: Pseudo URL prodotta da :meth:`build_url`.
          session: Ignorato, mantenuto per compatibilità con la superclasse.

        Returns:
          CSV con colonne ``date`` e ``value``.

        Raises:
          ModuleNotFoundError: Se ``yfinance`` non è installato.
          ValueError: Se il payload restituito non contiene le colonne attese.
        """

        if not url.startswith(self.BASE_URL):  # pragma: no cover - defensive
            return super()._download(url, session=session)
        request = self._parse_request(url)
        yf = self._import_yfinance()
        start = self._clamp_start(request.start)
        end_timestamp = self._ensure_utc(pd.Timestamp(self._now()))
        end = end_timestamp.date().isoformat()
        raw_frame = yf.download(
            tickers=request.symbol,
            start=start.date().isoformat(),
            end=end,
            progress=False,
            group_by="ticker",
            auto_adjust=True,
            threads=False,
        )
        if hasattr(raw_frame, "items") and not isinstance(raw_frame, pd.DataFrame):
            raw_frame = pd.DataFrame(raw_frame)
        if not isinstance(raw_frame, pd.DataFrame):
            raise ValueError("yfinance returned unexpected payload")
        raw_frame = raw_frame.sort_index()
        if raw_frame.empty:
            buffer = StringIO()
            buffer.write("date,value\n")
            csv_text = buffer.getvalue()
        else:
            frame = raw_frame.reset_index()
            date_column = self._detect_date_column(frame)
            value_column = self._detect_close_column(frame)
            canonical = pd.DataFrame(
                {
                    "date": pd.to_datetime(frame[date_column], errors="coerce", utc=True),
                    "value": pd.to_numeric(frame[value_column], errors="coerce"),
                }
            )
            canonical = canonical.dropna(subset=["date", "value"])
            buffer = StringIO()
            canonical.to_csv(buffer, index=False)
            csv_text = buffer.getvalue()
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        return csv_text

    def _parse_request(self, url: str) -> _YahooRequest:
        """Estrae simbolo e start ISO-8601 dalla pseudo URL generata."""

        parsed = urlparse(url)
        symbol = parsed.path or parsed.netloc
        symbol = symbol.lstrip("/")
        params = parse_qs(parsed.query)
        start_values = params.get("start")
        start = None
        if start_values:
            start = pd.to_datetime(start_values[0], utc=True, errors="coerce")
        return _YahooRequest(symbol=self._normalise_symbol(symbol), start=start)

    def _detect_date_column(self, frame: pd.DataFrame) -> str:
        """Individua la colonna data restituita da ``yfinance``."""

        for candidate in frame.columns:
            lowered = str(candidate).lower()
            if lowered in {"date", "datetime"}:
                return candidate
        return frame.columns[0]

    def _detect_close_column(self, frame: pd.DataFrame) -> str:
        """Seleziona la colonna close/adj close convertita in serie di valore."""

        candidates = {str(column).lower(): column for column in frame.columns}
        for key in ("adj close", "close"):
            if key in candidates:
                return candidates[key]
        raise ValueError("yfinance payload missing close/adj close column")

    def _clamp_start(self, requested: pd.Timestamp | None) -> pd.Timestamp:
        """Applica il limite massimo di lookback (5 anni)."""

        now_ts = self._ensure_utc(pd.Timestamp(self._now()))
        lower_bound = now_ts - pd.DateOffset(years=_MAX_LOOKBACK_YEARS)
        if requested is None or pd.isna(requested) or requested < lower_bound:
            return lower_bound
        return requested

    def _import_yfinance(self) -> object:
        """Importa ``yfinance`` segnalando chiaramente la dipendenza opzionale."""

        try:
            import yfinance as yf  # type: ignore[import]
        except ModuleNotFoundError as exc:  # pragma: no cover - dip opzionale
            msg = (
                "yfinance non è installato. Eseguire `pip install yfinance` per usare "
                "l'ingest Yahoo oppure specificare un'altra sorgente."
            )
            raise ModuleNotFoundError(msg) from exc
        return yf

    def _normalise_symbol(self, symbol: str) -> str:
        """Uniforma il simbolo in upper-case senza spazi superflui."""

        normalized = symbol.strip().upper()
        if not normalized:
            msg = "Yahoo: symbol must be non-empty"
            raise ValueError(msg)
        return normalized

    def _now(self) -> datetime:
        """Ritorna il timestamp corrente (UTC) — separato per facilitare i test."""

        return datetime.now(UTC)

    def _ensure_utc(self, timestamp: pd.Timestamp) -> pd.Timestamp:
        """Restituisce il timestamp convertito in UTC."""

        if timestamp.tzinfo is None:
            return timestamp.tz_localize(UTC)
        return timestamp.tz_convert(UTC)
