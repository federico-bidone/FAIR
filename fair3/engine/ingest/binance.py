"""Fetcher Binance Data Portal per klines giornalieri compressi."""

from __future__ import annotations

import io
import logging
import time
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from zipfile import BadZipFile, ZipFile

import pandas as pd
import requests

from .registry import BaseCSVFetcher, IngestArtifact, tqdm

__all__ = ["BinanceFetcher"]

_CSV_COLUMNS: Final[Sequence[str]] = (
    "open_time_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time_ms",
    "quote_volume",
    "trades",
    "taker_buy_base",
    "taker_buy_quote",
    "ignore",
)

_QUOTE_SUFFIXES: Final[tuple[str, ...]] = (
    "USDT",
    "USDC",
    "BUSD",
    "USDP",
    "EUR",
    "GBP",
    "TRY",
    "BRL",
    "BTC",
    "ETH",
)


class BinanceFetcher(BaseCSVFetcher):
    """Scarica klines giornalieri dal Binance Data Portal in formato ZIP.

    Il portale pubblica file ZIP giornalieri per coppia/interval con la stessa
    struttura dei klines REST. Il fetcher espande ogni archivio, normalizza le
    colonne principali e restituisce un DataFrame coerente con la pipeline FAIR
    aggiungendo metadati su intervallo, timezone e valuta quotata.
    """

    SOURCE: Final[str] = "binance"
    LICENSE: Final[str] = "Binance Data Portal — redistribution prohibited"
    BASE_URL: Final[str] = "https://data.binance.vision/data/spot/daily/klines"
    DEFAULT_SYMBOLS: Final[tuple[str, ...]] = ("BTCUSDT",)

    def __init__(
        self,
        *,
        interval: str = "1d",
        raw_root: Path | str | None = None,
        logger: logging.Logger | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Inizializza il fetcher configurando intervallo e destinazione raw.

        Args:
            interval: Intervallo Binance (es. ``"1d"`` oppure ``"1h"``) usato
                per risolvere i percorsi sul Data Portal.
            raw_root: Directory in cui serializzare i CSV normalizzati.
            logger: Logger opzionale per sovrascrivere quello predefinito.
            session: Sessione HTTP riutilizzabile per ridurre il numero di
                handshake TLS durante i download.
        """

        super().__init__(raw_root=raw_root, logger=logger, session=session)
        self.interval = interval

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce un URL rappresentativo per compatibilità con la base class.

        Args:
            symbol: Coppia Binance (es. ``BTCUSDT``).
            start: Timestamp iniziale disponibile; usato solo per stimare una
                data plausibile quando il metodo viene invocato da helper
                generici.

        Returns:
            URL completo verso il file ZIP della data indicata.
        """

        if start is not None:
            base_date = start.date().isoformat()
        else:
            base_date = datetime.now(UTC).date().isoformat()
        return self._compose_daily_url(symbol, base_date)

    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: datetime | pd.Timestamp | None = None,
        as_of: datetime | None = None,
        progress: bool = False,
        session: requests.Session | None = None,
    ) -> IngestArtifact:
        """Scarica i klines giornalieri concatenando i file ZIP tra start ed end.

        Args:
            symbols: Sequenza di coppie Binance da scaricare. Se ``None`` viene
                usata :pyattr:`DEFAULT_SYMBOLS`.
            start: Timestamp minimo (UTC o naive) per limitare le osservazioni.
            as_of: Timestamp di riferimento usato per etichettare l'artefatto.
            progress: Se ``True`` abilita la barra ``tqdm`` sui giorni scaricati.
            session: Sessione HTTP opzionale per riutilizzare le connessioni.

        Returns:
            Artefatto di ingest con dati concatenati e metadati di audit.

        Raises:
            ValueError: Se non viene fornito alcun simbolo da scaricare.
        """

        symbol_list = list(self.DEFAULT_SYMBOLS if symbols is None else symbols)
        if not symbol_list:
            raise ValueError("At least one symbol must be provided")

        timestamp = as_of or datetime.now(UTC)
        end_ts = self._ensure_utc(timestamp)
        start_ts = self._derive_start_timestamp(start, end_ts)

        frames: list[pd.DataFrame] = []
        requests_meta: list[dict[str, str]] = []

        for symbol in symbol_list:
            symbol_frame, symbol_requests = self._collect_symbol_data(
                symbol,
                start_ts,
                end_ts,
                progress=progress,
                session=session,
            )
            if not symbol_frame.empty:
                frames.append(symbol_frame)
            requests_meta.extend(symbol_requests)
            self.logger.info(
                "ingest_complete source=%s symbol=%s rows=%d license=%s start=%s end=%s",
                self.SOURCE,
                symbol,
                len(symbol_frame),
                self.LICENSE,
                start_ts.date().isoformat(),
                end_ts.date().isoformat(),
            )

        if frames:
            data = pd.concat(frames, ignore_index=True)
        else:
            data = pd.DataFrame(columns=["date", "value", "symbol"])
        path = self._write_csv(data, end_ts)
        metadata = {
            "license": self.LICENSE,
            "as_of": end_ts.isoformat(),
            "requests": requests_meta,
            "start": start_ts.isoformat(),
        }
        return IngestArtifact(source=self.SOURCE, path=path, data=data, metadata=metadata)

    def parse(self, payload: bytes | str, symbol: str) -> pd.DataFrame:
        """Converte un archivio ZIP Binance in DataFrame normalizzato.

        Args:
            payload: Bytes (o stringa) corrispondenti al file ZIP scaricato.
            symbol: Coppia Binance richiesta dall'utente.

        Returns:
            DataFrame con colonne ``date``, ``value``, ``symbol`` e metriche
            aggiuntive (open/high/low/volumi) normalizzate in UTC.

        Raises:
            ValueError: Se il payload è HTML, corrotto o privo di file CSV.
        """

        raw = payload.encode("utf-8") if isinstance(payload, str) else payload
        prefix = raw[:32].lstrip()
        if prefix.startswith(b"<"):
            msg = "Binance: HTML payload detected (probable error page)"
            raise ValueError(msg)
        try:
            with ZipFile(io.BytesIO(raw)) as archive:
                member = self._select_member(archive)
                with archive.open(member) as handle:
                    frame = pd.read_csv(handle, header=None, names=_CSV_COLUMNS)
        except (BadZipFile, KeyError, UnicodeDecodeError, ValueError) as exc:
            msg = "Binance: invalid ZIP payload"
            raise ValueError(msg) from exc

        if frame.empty:
            return pd.DataFrame(columns=["date", "value", "symbol"])

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "taker_buy_base",
            "taker_buy_quote",
        ]
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["trades"] = pd.to_numeric(frame["trades"], errors="coerce").astype("Int64")

        frame["open_time"] = pd.to_datetime(frame["open_time_ms"], unit="ms", utc=True)
        frame["close_time"] = pd.to_datetime(frame["close_time_ms"], unit="ms", utc=True)

        result = pd.DataFrame(
            {
                "date": frame["open_time"].dt.tz_convert(UTC).dt.tz_localize(None),
                "value": frame["close"],
                "symbol": symbol,
                "open": frame["open"],
                "high": frame["high"],
                "low": frame["low"],
                "close": frame["close"],
                "volume": frame["volume"],
                "quote_volume": frame["quote_volume"],
                "trades": frame["trades"],
                "taker_buy_base": frame["taker_buy_base"],
                "taker_buy_quote": frame["taker_buy_quote"],
                "open_time": frame["open_time"].dt.tz_convert(UTC).dt.tz_localize(None),
                "close_time": frame["close_time"].dt.tz_convert(UTC).dt.tz_localize(None),
                "interval": self.interval,
                "currency": self._quote_currency(symbol),
                "tz": "UTC",
                "pit_flag": 1,
            }
        )
        return result.dropna(subset=["date", "value"]).reset_index(drop=True)

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> bytes:
        """Scarica un file ZIP restituendo i bytes grezzi.

        Args:
            url: URL da interrogare.
            session: Sessione HTTP opzionale da riutilizzare.

        Returns:
            Byte string contenente l'archivio ZIP scaricato.
        """

        active_session = session or self.session
        close_session = False
        if active_session is None:
            active_session = requests.Session()
            close_session = True
        try:
            for attempt in range(1, self.RETRIES + 1):
                response = active_session.get(url, headers=self.HEADERS, timeout=30)
                if response.ok:
                    return response.content
                if attempt == self.RETRIES:
                    response.raise_for_status()
                time.sleep(self.BACKOFF_SECONDS * attempt)
        finally:
            if close_session:
                active_session.close()
        raise RuntimeError(f"Unable to download from {url}")

    def _collect_symbol_data(
        self,
        symbol: str,
        start: pd.Timestamp,
        end: pd.Timestamp,
        *,
        progress: bool,
        session: requests.Session | None = None,
    ) -> tuple[pd.DataFrame, list[dict[str, str]]]:
        """Scarica tutti i giorni disponibili per un simbolo e li concatena.

        Args:
            symbol: Coppia Binance richiesta.
            start: Timestamp UTC iniziale (inclusivo).
            end: Timestamp UTC finale (inclusivo).
            progress: Flag per abilitare la barra ``tqdm`` sui giorni processati.
            session: Sessione HTTP opzionale.

        Returns:
            Tupla con il DataFrame concatenato e i metadati delle richieste.
        """

        dates = pd.date_range(start=start.floor("D"), end=end.floor("D"), freq="D")
        frames: list[pd.DataFrame] = []
        requests_meta: list[dict[str, str]] = []
        iterator = tqdm(
            dates,
            disable=not progress,
            desc=f"ingest:{self.SOURCE}:{symbol}",
            unit="day",
        )
        for day in iterator:
            url = self._compose_daily_url(symbol, day.date().isoformat())
            request_record = {"symbol": symbol, "url": url, "date": day.date().isoformat()}
            try:
                payload = self._download(url, session=session)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    self.logger.warning(
                        "binance_missing_day symbol=%s date=%s url=%s",
                        symbol,
                        day.date().isoformat(),
                        url,
                    )
                    request_record["status"] = "missing"
                    requests_meta.append(request_record)
                    continue
                raise
            frame = self.parse(payload, symbol)
            frames.append(frame)
            request_record["status"] = "ok"
            requests_meta.append(request_record)
        if frames:
            data = pd.concat(frames, ignore_index=True)
        else:
            data = pd.DataFrame(columns=["date", "value", "symbol"])
        start_naive = self._to_naive_utc(start)
        end_naive = self._to_naive_utc(end)
        data = data[(data["date"] >= start_naive) & (data["date"] <= end_naive)]
        data = data.sort_values("date").reset_index(drop=True)
        return data, requests_meta

    def _compose_daily_url(self, symbol: str, day: str) -> str:
        """Costruisce l'URL del file ZIP giornaliero per simbolo e data.

        Args:
            symbol: Coppia Binance (es. ``BTCUSDT``).
            day: Giorno ISO ``YYYY-MM-DD``.

        Returns:
            URL completo del file ZIP giornaliero.
        """

        return f"{self.BASE_URL}/{symbol}/{self.interval}/{symbol}-{self.interval}-{day}.zip"

    def _select_member(self, archive: ZipFile) -> str:
        """Seleziona in modo deterministico il file CSV da un archivio ZIP.

        Args:
            archive: Archivio ZIP aperto.

        Returns:
            Nome del membro CSV scelto.

        Raises:
            ValueError: Se l'archivio non contiene file CSV.
        """

        candidates = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not candidates:
            raise ValueError("Binance: ZIP archive missing CSV member")
        candidates.sort()
        return candidates[0]

    def _ensure_utc(self, value: datetime | pd.Timestamp) -> pd.Timestamp:
        """Converte un datetime arbitrario in timestamp UTC con tz esplicita.

        Args:
            value: Timestamp o datetime da convertire.

        Returns:
            Timestamp pandas timezone-aware in UTC.
        """

        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize(UTC)
        return ts.tz_convert(UTC)

    def _derive_start_timestamp(
        self, start: datetime | pd.Timestamp | None, end: pd.Timestamp
    ) -> pd.Timestamp:
        """Deriva il timestamp iniziale limitando l'intervallo a 365 giorni default.

        Args:
            start: Timestamp richiesto dall'utente o ``None``.
            end: Timestamp finale già convertito in UTC.

        Returns:
            Timestamp UTC non successivo a ``end``.
        """

        if start is None:
            candidate = end - pd.Timedelta(days=365)
        else:
            candidate = self._ensure_utc(start)
        if candidate > end:
            return end
        return candidate

    def _quote_currency(self, symbol: str) -> str:
        """Deduce la valuta quotata dal simbolo Binance.

        Args:
            symbol: Coppia Binance completa.

        Returns:
            Codice della valuta quotata oppure ``"UNKNOWN"`` se non inferibile.
        """

        upper = symbol.upper()
        for suffix in _QUOTE_SUFFIXES:
            if upper.endswith(suffix):
                return suffix
        return "UNKNOWN"

    def _to_naive_utc(self, timestamp: pd.Timestamp) -> pd.Timestamp:
        """Rimuove il timezone mantenendo il valore UTC come datetime naive.

        Args:
            timestamp: Timestamp timezone-aware da convertire.

        Returns:
            Timestamp pandas privo di timezone ma rappresentante lo stesso istante.
        """

        return timestamp.tz_convert(UTC).tz_localize(None)
