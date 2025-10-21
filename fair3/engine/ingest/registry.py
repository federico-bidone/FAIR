from __future__ import annotations

import logging
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from fair3.engine.utils.io import ensure_dir
from fair3.engine.utils.log import get_logger

__all__ = [
    "IngestArtifact",
    "BaseCSVFetcher",
    "available_sources",
    "create_fetcher",
    "run_ingest",
]


@dataclass(slots=True)
class IngestArtifact:
    """Metadata bundle returned after an ingest run."""

    source: str
    path: Path
    data: pd.DataFrame
    metadata: Mapping[str, Any]


class BaseCSVFetcher:
    """Minimal HTTP CSV fetcher with retry/backoff and CSV normalization."""

    SOURCE: str = ""
    LICENSE: str = ""
    BASE_URL: str = ""
    DEFAULT_SYMBOLS: Sequence[str] = ()
    RETRIES: int = 3
    BACKOFF_SECONDS: float = 0.5
    HEADERS: Mapping[str, str] = {"User-Agent": "fair3-ingest/0.1"}

    def __init__(
        self,
        *,
        raw_root: Path | str | None = None,
        logger: logging.Logger | None = None,
        session: requests.Session | None = None,
    ) -> None:
        if not self.SOURCE:
            raise ValueError("SOURCE must be defined on subclasses")
        if not self.LICENSE:
            raise ValueError("LICENSE must be defined on subclasses")
        self.raw_root = Path(raw_root) if raw_root is not None else Path("data") / "raw"
        self.logger = logger or get_logger(f"fair3.ingest.{self.SOURCE}")
        self.session = session

    # --- public API -----------------------------------------------------
    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: date | datetime | None = None,
        as_of: datetime | None = None,
        session: requests.Session | None = None,
    ) -> IngestArtifact:
        if symbols is None:
            symbol_list = list(self.DEFAULT_SYMBOLS)
        else:
            symbol_list = list(symbols)
        if not symbol_list:
            raise ValueError("At least one symbol must be provided")

        timestamp = as_of or datetime.now(UTC)
        frames: list[pd.DataFrame] = []
        requests_meta: list[dict[str, Any]] = []
        start_ts = pd.to_datetime(start) if start is not None else None

        for symbol in symbol_list:
            url = self.build_url(symbol, start_ts)
            payload = self._download(url, session=session)
            frame = self.parse(payload, symbol)
            if start_ts is not None:
                frame = frame[frame["date"] >= start_ts]
            frame = frame.sort_values("date").reset_index(drop=True)
            frames.append(frame)
            requests_meta.append({"symbol": symbol, "url": url})
            self.logger.info(
                "ingest_complete source=%s symbol=%s rows=%d license=%s url=%s",
                self.SOURCE,
                symbol,
                len(frame),
                self.LICENSE,
                url,
            )

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
        artifact = IngestArtifact(
            source=self.SOURCE,
            path=path,
            data=data,
            metadata=metadata,
        )
        return artifact

    # --- subclass hooks -------------------------------------------------
    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        raise NotImplementedError

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        raise NotImplementedError

    # --- helpers --------------------------------------------------------
    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        active_session = session or self.session
        close_session = False
        if active_session is None:
            active_session = requests.Session()
            close_session = True
        try:
            for attempt in range(1, self.RETRIES + 1):
                response = active_session.get(url, headers=self.HEADERS, timeout=30)
                if response.ok:
                    response.encoding = response.encoding or "utf-8"
                    return response.text
                if attempt == self.RETRIES:
                    response.raise_for_status()
                time.sleep(self.BACKOFF_SECONDS * attempt)
        finally:
            if close_session:
                active_session.close()
        raise RuntimeError(f"Unable to download from {url}")

    def _simple_frame(
        self,
        payload: str,
        symbol: str,
        *,
        date_column: str,
        value_column: str,
        rename: Mapping[str, str] | None = None,
    ) -> pd.DataFrame:
        csv = pd.read_csv(StringIO(payload))
        if rename:
            csv = csv.rename(columns=rename)
        if date_column not in csv.columns or value_column not in csv.columns:
            msg = f"Expected columns {date_column}/{value_column} in payload"
            raise ValueError(msg)
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(csv[date_column], errors="coerce"),
                "value": pd.to_numeric(csv[value_column], errors="coerce"),
                "symbol": symbol,
            }
        )
        frame = frame.dropna(subset=["date", "value"]).reset_index(drop=True)
        return frame

    def _write_csv(self, data: pd.DataFrame, timestamp: datetime) -> Path:
        target_dir = ensure_dir(self.raw_root / self.SOURCE)
        file_name = f"{self.SOURCE}_{timestamp.strftime('%Y%m%dT%H%M%SZ')}.csv"
        target_path = target_dir / file_name
        data_to_write = data.copy()
        if not data_to_write.empty:
            data_to_write["date"] = data_to_write["date"].dt.strftime("%Y-%m-%d")
        data_to_write.to_csv(target_path, index=False)
        return target_path


def _fetcher_map() -> Mapping[str, type[BaseCSVFetcher]]:
    from .boe import BOEFetcher
    from .ecb import ECBFetcher
    from .fred import FREDFetcher
    from .stooq import StooqFetcher

    return {
        BOEFetcher.SOURCE: BOEFetcher,
        ECBFetcher.SOURCE: ECBFetcher,
        FREDFetcher.SOURCE: FREDFetcher,
        StooqFetcher.SOURCE: StooqFetcher,
    }


def available_sources() -> Sequence[str]:
    """Return the list of supported ingest sources."""

    return tuple(sorted(_fetcher_map().keys()))


def create_fetcher(source: str, **kwargs: object) -> BaseCSVFetcher:
    try:
        fetcher_cls = _fetcher_map()[source]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unsupported ingest source: {source}") from exc
    return fetcher_cls(**kwargs)


def run_ingest(
    source: str,
    *,
    symbols: Iterable[str] | None = None,
    start: date | datetime | None = None,
    raw_root: Path | str | None = None,
    as_of: datetime | None = None,
) -> IngestArtifact:
    fetcher = create_fetcher(source, raw_root=raw_root)
    return fetcher.fetch(symbols=symbols, start=start, as_of=as_of)
