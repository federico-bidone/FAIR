"""Fetcher World Bank v2 con gestione pagine JSON e normalizzazione FAIR."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import pandas as pd

from .registry import BaseCSVFetcher, IngestArtifact

__all__ = ["WorldBankFetcher"]


if TYPE_CHECKING:
    from requests import Session
else:  # pragma: no cover - fallback per annotazioni runtime
    Session = object


class WorldBankFetcher(BaseCSVFetcher):
    """Scarica indicatori World Bank aggregando tutte le pagine disponibili."""

    SOURCE = "worldbank"
    LICENSE = "World Bank Open Data Terms"
    BASE_URL = "https://api.worldbank.org/v2"
    DEFAULT_SYMBOLS = (
        "SP.POP.TOTL:ITA",
        "NY.GDP.MKTP.KD:ITA",
    )

    HEADERS = {
        "User-Agent": "fair3-ingest/0.2",
        "Accept": "application/json",
    }

    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: datetime | date | None = None,
        as_of: datetime | None = None,
        progress: bool = False,
        session: Session | None = None,
    ) -> IngestArtifact:
        """Scarica indicatori World Bank gestendo la paginazione JSON.

        Args:
            symbols: Sequenza opzionale di indicatori nel formato
                ``<indicatore>:<paese1;paese2>``.
            start: Timestamp minimo da cui mantenere le osservazioni; usato anche
                per impostare il parametro ``date`` della richiesta.
            as_of: Timestamp di riferimento per nominare il file raw.
            progress: Se ``True`` abilita la barra ``tqdm`` sui simboli.
            session: Sessione HTTP riutilizzabile; se assente ne viene creata una
                temporanea.

        Returns:
            Artefatto contenente dati normalizzati e metadati di audit.

        Raises:
            ValueError: Se non vengono indicati simboli da scaricare.
        """

        symbol_list = list(self.DEFAULT_SYMBOLS if symbols is None else symbols)
        if not symbol_list:
            raise ValueError("At least one symbol must be provided")

        timestamp = as_of or datetime.now(UTC)
        frames: list[pd.DataFrame] = []
        requests_meta: list[dict[str, Any]] = []
        start_ts = pd.to_datetime(start) if start is not None else None

        iterator = self._progress_iterator(symbol_list, progress)
        active_session, close_session = self._ensure_session(session)

        try:
            for symbol in iterator:
                symbol_frames = []
                last_url = ""
                for page, url, metadata, page_frame in self._download_pages(
                    symbol,
                    start_ts,
                    active_session,
                ):
                    if page_frame is not None:
                        symbol_frames.append(page_frame)
                    requests_meta.append(
                        {
                            "symbol": symbol,
                            "url": url,
                            "page": page,
                            "pages": metadata.get("pages", 1),
                        }
                    )
                    last_url = url
                    if page >= metadata.get("pages", 1):
                        break
                frame = self._combine_symbol_frames(symbol_frames, start_ts)
                frames.append(frame)
                self.logger.info(
                    "ingest_complete source=%s symbol=%s rows=%d license=%s url=%s",
                    self.SOURCE,
                    symbol,
                    len(frame),
                    self.LICENSE,
                    last_url,
                )
        finally:
            if close_session:
                active_session.close()

        if frames:
            data = pd.concat(frames, ignore_index=True)
        else:
            data = pd.DataFrame(columns=["date", "value", "symbol"])
        path = self._write_csv(data, timestamp)
        metadata = {
            "license": self.LICENSE,
            "as_of": timestamp.isoformat(),
            "requests": requests_meta,
            "start": start_ts.isoformat() if start_ts is not None else None,
        }
        return IngestArtifact(self.SOURCE, path, data, metadata)

    def build_url(self, symbol: str, start: pd.Timestamp | None, page: int = 1) -> str:
        """Compone l'URL World Bank per un indicatore e una o più nazioni.

        Args:
            symbol: Stringa ``<indicatore>:<paesi>`` con codici ISO3 separati da
                `;` o `,`.
            start: Timestamp minimo; se presente imposta il parametro ``date``
                come ``<anno_start>:<anno_corrente>``.
            page: Numero di pagina richiesto (1-indexed).

        Returns:
            URL completo utilizzato per la richiesta HTTP.

        Raises:
            ValueError: Se il simbolo non contiene sia indicatore sia paese.
        """

        indicator, sep, countries = symbol.partition(":")
        if not sep or not indicator or not countries:
            msg = "World Bank symbol must be formatted as <indicator>:<country>"
            raise ValueError(msg)
        cleaned_countries = countries.replace(",", ";").replace(" ", "").upper()
        params = {
            "format": "json",
            "per_page": "20000",
            "page": str(page),
        }
        if start is not None:
            params["date"] = f"{start.year}:{datetime.now(UTC).year}"
        query = "&".join(f"{key}={value}" for key, value in params.items())
        return f"{self.BASE_URL}/country/{cleaned_countries}/indicator/{indicator}?{query}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Compatibilità con l'interfaccia base, restituisce il DataFrame normalizzato.

        Args:
            payload: Testo JSON ricevuto dall'API World Bank.
            symbol: Simbolo richiesto originariamente dal chiamante.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``; se il payload
            non contiene osservazioni viene restituito un DataFrame vuoto.
        """

        _, frame = self._parse_payload(payload, symbol)
        return frame if frame is not None else pd.DataFrame(columns=["date", "value", "symbol"])

    def _download_pages(
        self,
        symbol: str,
        start: pd.Timestamp | None,
        session: Session,
    ) -> Iterator[tuple[int, str, dict[str, int], pd.DataFrame | None]]:
        """Scarica sequenzialmente tutte le pagine per un simbolo.

        Args:
            symbol: Simbolo World Bank ``<indicatore>:<paesi>``.
            start: Timestamp minimo usato nel calcolo della query ``date``.
            session: Sessione HTTP da riutilizzare per le richieste.

        Yields:
            Tuple ``(page, url, metadata, frame)`` per ogni pagina disponibile.
        """

        page = 1
        while True:
            url = self.build_url(symbol, start, page=page)
            payload = self._download(url, session=session)
            metadata, frame = self._parse_payload(payload, symbol)
            yield page, url, metadata, frame
            if page >= metadata.get("pages", 1):
                break
            page += 1

    def _parse_payload(
        self, payload: str, symbol: str
    ) -> tuple[dict[str, int], pd.DataFrame | None]:
        """Converte il JSON World Bank in DataFrame normalizzato.

        Args:
            payload: Testo JSON restituito dall'API.
            symbol: Simbolo richiesto, usato per ricostruire il codice indicator.

        Returns:
            Coppia ``(metadata, frame)`` dove ``metadata`` contiene pagine totali
            e ``frame`` è il DataFrame normalizzato (o ``None`` se vuoto).

        Raises:
            ValueError: Se il payload è HTML o non è decodificabile come JSON.
        """

        if payload.lstrip().startswith("<"):
            msg = "World Bank: HTML payload detected (possible error page)"
            raise ValueError(msg)
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:  # pragma: no cover - errore di rete
            raise ValueError("World Bank: invalid JSON payload") from exc
        if not isinstance(decoded, list) or not decoded:
            return {}, pd.DataFrame(columns=["date", "value", "symbol"])
        metadata_raw = decoded[0] if isinstance(decoded[0], dict) else {}
        entries = decoded[1] if len(decoded) > 1 and isinstance(decoded[1], list) else []
        metadata = self._coerce_metadata(metadata_raw)
        frame = self._entries_to_frame(entries, symbol)
        return metadata, frame

    def _coerce_metadata(self, metadata_raw: dict[str, Any]) -> dict[str, int]:
        """Converte i metadati World Bank in interi utilizzabili.

        Args:
            metadata_raw: Dizionario grezzo con campi stringa o interi.

        Returns:
            Mapping con chiavi ``page``, ``pages`` e ``per_page`` normalizzate.
        """

        metadata: dict[str, int] = {}
        for key in ("page", "pages", "per_page"):
            value = metadata_raw.get(key)
            if isinstance(value, int):
                metadata[key] = value
            elif isinstance(value, str) and value.isdigit():
                metadata[key] = int(value)
        return metadata

    def _entries_to_frame(self, entries: list[Any], symbol: str) -> pd.DataFrame | None:
        """Trasforma la lista di osservazioni in DataFrame normalizzato.

        Args:
            entries: Lista di osservazioni provenienti dall'API.
            symbol: Simbolo originale richiesto.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol`` oppure ``None``
            se non sono presenti righe valide.
        """

        records: list[dict[str, Any]] = []
        indicator_code = symbol.split(":", 1)[0]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            iso_code = entry.get("countryiso3code")
            year = entry.get("date")
            value = entry.get("value")
            indicator = entry.get("indicator", {}) or {}
            indicator_id = indicator.get("id") if isinstance(indicator, dict) else None
            if iso_code:
                symbol_value = f"{indicator_id or indicator_code}:{iso_code}"
            else:
                symbol_value = symbol
            records.append(
                {
                    "date": pd.to_datetime(year, errors="coerce"),
                    "value": pd.to_numeric(value, errors="coerce"),
                    "symbol": symbol_value,
                }
            )
        if not records:
            return None
        frame = pd.DataFrame.from_records(records)
        frame = frame.dropna(subset=["date", "value"]).reset_index(drop=True)
        return frame

    def _combine_symbol_frames(
        self,
        frames: list[pd.DataFrame],
        start_ts: pd.Timestamp | None,
    ) -> pd.DataFrame:
        """Unisce le pagine di un simbolo applicando filtro per data.

        Args:
            frames: Lista di DataFrame provenienti dalle varie pagine.
            start_ts: Timestamp minimo per filtrare le osservazioni.

        Returns:
            DataFrame ordinato per data con righe del simbolo considerato.
        """

        if frames:
            frame = pd.concat(frames, ignore_index=True)
        else:
            frame = pd.DataFrame(columns=["date", "value", "symbol"])
        if start_ts is not None:
            frame = frame[frame["date"] >= start_ts]
        return frame.sort_values("date").reset_index(drop=True)

    def _progress_iterator(self, symbols: list[str], enabled: bool) -> Iterable[str]:
        """Restituisce un iteratore opzionalmente avvolto da tqdm.

        Args:
            symbols: Elenco dei simboli da iterare.
            enabled: Se ``True`` prova ad avvolgere la sequenza con ``tqdm``.

        Returns:
            L'iterabile originale o l'oggetto ``tqdm`` se disponibile.
        """

        if not enabled:
            return symbols
        try:  # pragma: no cover - dipendenza opzionale
            from tqdm.auto import tqdm
        except ModuleNotFoundError:  # pragma: no cover - fallback
            return symbols
        return tqdm(symbols, desc=f"ingest:{self.SOURCE}", unit="symbol")

    def _ensure_session(self, session: Session | None) -> tuple[Session, bool]:
        """Restituisce la sessione HTTP e se deve essere chiusa al termine.

        Args:
            session: Sessione già aperta o ``None``.

        Returns:
            Coppia ``(sessione, chiudere)`` dove ``chiudere`` è ``True`` se la
            sessione deve essere chiusa dal chiamante.
        """

        if session is not None:
            return session, False
        if self.session is not None:
            return self.session, False
        import requests

        active_session = requests.Session()
        return active_session, True
