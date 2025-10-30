from __future__ import annotations

import logging
import sqlite3
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from tqdm.auto import tqdm

try:  # pragma: no cover - optional dependency shim
    from tqdm.auto import tqdm
except ModuleNotFoundError:  # pragma: no cover - fallback

    def tqdm(iterable: Iterable[str] | None = None, **_: object) -> Iterable[str]:
        """Minimal tqdm stub returning the iterable unchanged."""

        return iterable if iterable is not None else []


from fair3.engine.logging import setup_logger
from fair3.engine.utils.io import ensure_dir, sha256_file
from fair3.engine.utils.storage import ensure_metadata_schema, upsert_sqlite

__all__ = [
    "IngestArtifact",
    "BaseCSVFetcher",
    "CredentialField",
    "available_sources",
    "credential_fields",
    "source_licenses",
    "create_fetcher",
    "run_ingest",
]


@dataclass(frozen=True, slots=True)
class CredentialField:
    """Metadata describing credentials required by specific providers."""

    source: str
    env: str
    label: str
    description: str
    url: str | None = None


PROVIDER_CREDENTIALS: tuple[CredentialField, ...] = (
    CredentialField(
        source="alphavantage_fx",
        env="ALPHAVANTAGE_API_KEY",
        label="Alpha Vantage FX",
        description="FX_DAILY endpoint for currency crosses",
        url="https://www.alphavantage.co/support/#api-key",
    ),
    CredentialField(
        source="tiingo",
        env="TIINGO_API_KEY",
        label="Tiingo",
        description="Equity and ETF OHLCV feed",
        url="https://www.tiingo.com/account/api/token",
    ),
    CredentialField(
        source="eodhd",
        env="EODHD_API_TOKEN",
        label="EOD Historical Data",
        description="EOD equity prices and fundamentals",
        url="https://eodhistoricaldata.com/financial-apis/",
    ),
    CredentialField(
        source="fred",
        env="FRED_API_KEY",
        label="FRED",
        description="Federal Reserve macroeconomic time series",
        url="https://fred.stlouisfed.org/faq#api_key",
    ),
)


def credential_fields() -> tuple[CredentialField, ...]:
    """Expose credential metadata for GUI consumers."""

    return PROVIDER_CREDENTIALS


@dataclass(slots=True)
class IngestArtifact:
    """Contenitore immutabile con dati e metadati prodotti da una run di ingest."""

    source: str
    path: Path
    data: pd.DataFrame
    metadata: Mapping[str, Any]


class BaseCSVFetcher:
    """Fetcher HTTP minimale per CSV con retry/backoff e normalizzazione coerente."""

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
        clean_database: Path | str | None = None,
        logger: logging.Logger | None = None,
        session: requests.Session | None = None,
    ) -> None:
        # Valida le costanti dichiarative: ogni fetcher deve identificare sorgente e licenza.
        if not self.SOURCE:
            raise ValueError("SOURCE must be defined on subclasses")
        if not self.LICENSE:
            raise ValueError("LICENSE must be defined on subclasses")
        self.raw_root = Path(raw_root) if raw_root is not None else Path("data") / "raw"
        self.logger = logger or setup_logger(f"fair3.ingest.{self.SOURCE}")
        self.database_path = (
            Path(clean_database)
            if clean_database is not None
            else Path("data") / "fair_metadata.sqlite"
        )
        self.session = session

    # --- API pubblica ---------------------------------------------------
    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: date | datetime | None = None,
        as_of: datetime | None = None,
        progress: bool = False,
        session: requests.Session | None = None,
    ) -> IngestArtifact:
        """Scarica i simboli richiesti restituendo dati normalizzati e log auditabili.

        Args:
            symbols: Lista opzionale di simboli specifici per la sorgente.
            start: Data/ora minima da cui mantenere le osservazioni.
            as_of: Timestamp di riferimento per nominare gli artefatti.
            progress: Se ``True`` mostra una barra `tqdm` per le richieste.
            session: Sessione HTTP riutilizzabile; creata internamente se assente.

        Returns:
            Artefatto con DataFrame normalizzato e metadati di audit.

        Raises:
            ValueError: Se non viene fornito alcun simbolo da scaricare.
        """
        if symbols is None:
            symbol_list = list(self.DEFAULT_SYMBOLS)
        else:
            symbol_list = list(symbols)
        if not symbol_list:
            raise ValueError("At least one symbol must be provided")

        timestamp = as_of or datetime.now(UTC)
        frames: list[pd.DataFrame] = []
        requests_meta: list[dict[str, Any]] = []
        log_rows: list[dict[str, Any]] = []
        instrument_rows: dict[str, dict[str, Any]] = {}
        source_map_rows: list[dict[str, Any]] = []
        start_ts = pd.to_datetime(start) if start is not None else None

        # Per ogni simbolo ripetiamo download → parsing → filtro → log, mantenendo
        # un tracking puntuale dei metadati da restituire alla fine.
        iterator = tqdm(
            symbol_list,
            disable=not progress,
            desc=f"ingest:{self.SOURCE}",
            unit="symbol",
        )
        for symbol in iterator:
            url = self.build_url(symbol, start_ts)
            start_time = time.perf_counter()
            payload = self._download(url, session=session)
            duration = time.perf_counter() - start_time
            frame = self.parse(payload, symbol)
            if start_ts is not None:
                frame = frame[frame["date"] >= start_ts]
            frame = frame.sort_values("date").reset_index(drop=True)
            frames.append(frame)
            requests_meta.append({"symbol": symbol, "url": url})
            if isinstance(payload, bytes):
                payload_bytes = len(payload)
            else:
                payload_bytes = len(payload.encode("utf-8"))
            currency = frame.get("currency")
            currency_value = (
                currency.iloc[0] if isinstance(currency, pd.Series) and not currency.empty else None
            )
            instrument_rows[symbol] = {
                "id": symbol,
                "isin": None,
                "figi": None,
                "mic": None,
                "symbol": symbol,
                "asset_class": None,
                "currency": currency_value,
                "lot": None,
                "adv_hint": None,
                "fee_hint": None,
                "bidask_hint": None,
                "provider_pref": self.SOURCE,
                "ucits_flag": None,
                "govies_share_hint": None,
                "ter_hint": None,
                "kid_url": None,
            }
            source_map_rows.append(
                {
                    "instrument_id": symbol,
                    "preferred_source": self.SOURCE,
                    "fallback_source": None,
                    "url": url,
                    "license": self.LICENSE,
                    "rate_limit_note": None,
                    "last_success": timestamp,
                    "etag": None,
                    "last_modified": None,
                }
            )
            log_rows.append(
                {
                    "ts": timestamp,
                    "source": self.SOURCE,
                    "endpoint": url,
                    "symbol": symbol,
                    "status": "success",
                    "http_code": 200,
                    "bytes": payload_bytes,
                    "rows": int(len(frame)),
                    "duration_s": duration,
                    "retries": 0,
                    "warning": "",
                    "checksum_sha256": None,
                }
            )
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
        checksum = sha256_file(path) if path.exists() else None
        if checksum is not None:
            for row in log_rows:
                row["checksum_sha256"] = checksum
        # I metadati conservano licenza, timestamp e richieste effettuate per audit trail.
        metadata = {
            "license": self.LICENSE,
            "as_of": timestamp.isoformat(),
            "requests": requests_meta,
            "start": start_ts.isoformat() if start_ts is not None else None,
            "checksum_sha256": checksum,
        }
        artifact = IngestArtifact(
            source=self.SOURCE,
            path=path,
            data=data,
            metadata=metadata,
        )
        if log_rows:
            self._persist_metadata(log_rows, instrument_rows, source_map_rows)
        return artifact

    # --- hook per sottoclassi ------------------------------------------
    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Hook di estensione: restituisce l'URL completo per un simbolo specifico."""
        raise NotImplementedError

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Hook di estensione: interpreta il payload in un DataFrame conforme."""
        raise NotImplementedError

    # --- helper --------------------------------------------------------
    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        """Scarica il payload come stringa gestendo retry incrementale e chiusura sessione."""
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
        """Normalizza un CSV in un DataFrame canonico (date, valore, simbolo)."""
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
        """Serializza i dati normalizzati su disco garantendo naming deterministico."""
        target_dir = ensure_dir(self.raw_root / self.SOURCE)
        file_name = f"{self.SOURCE}_{timestamp.strftime('%Y%m%dT%H%M%SZ')}.csv"
        target_path = target_dir / file_name
        data_to_write = data.copy()
        if not data_to_write.empty:
            data_to_write["date"] = data_to_write["date"].dt.strftime("%Y-%m-%d")
        data_to_write.to_csv(target_path, index=False)
        return target_path

    def _persist_metadata(
        self,
        log_rows: list[dict[str, Any]],
        instrument_rows: Mapping[str, dict[str, Any]],
        source_map_rows: list[dict[str, Any]],
    ) -> None:
        """Aggiorna le tabelle SQLite con i dati di ingest appena raccolti."""

        ensure_dir(self.database_path.parent)
        conn = sqlite3.connect(self.database_path)
        try:
            ensure_metadata_schema(conn)
            log_frame = pd.DataFrame(log_rows)
            log_frame["ts"] = (
                pd.to_datetime(log_frame["ts"], utc=True)
                .dt.tz_convert("UTC")
                .dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            upsert_sqlite(conn, "ingest_log", log_frame, ["ts", "source", "symbol", "endpoint"])

            instrument_frame = pd.DataFrame(instrument_rows.values())
            upsert_sqlite(conn, "instrument", instrument_frame, ["id"])

            source_map_frame = pd.DataFrame(source_map_rows)
            source_map_frame["last_success"] = (
                pd.to_datetime(source_map_frame["last_success"], utc=True)
                .dt.tz_convert("UTC")
                .dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            upsert_sqlite(
                conn,
                "source_map",
                source_map_frame,
                ["instrument_id", "preferred_source"],
            )
        finally:
            conn.close()


def _fetcher_map() -> Mapping[str, type[BaseCSVFetcher]]:
    from .alpha import AlphaFetcher
    from .alphavantage import AlphaVantageFXFetcher
    from .aqr import AQRFetcher
    from .binance import BinanceFetcher
    from .bis import BISFetcher
    from .boe import BOEFetcher
    from .cboe import CBOEFetcher
    from .coingecko import CoinGeckoFetcher
    from .curvo import CurvoFetcher
    from .ecb import ECBFetcher
    from .eodhd import EODHDFetcher
    from .fred import FREDFetcher
    from .french import FrenchFetcher
    from .lbma import LBMAFetcher
    from .nareit import NareitFetcher
    from .oecd import OECDFetcher
    from .portfolio_visualizer import PortfolioVisualizerFetcher
    from .portfoliocharts import PortfolioChartsFetcher
    from .stooq import StooqFetcher
    from .testfolio import TestfolioPresetFetcher
    from .tiingo import TiingoFetcher
    from .us_market_data import USMarketDataFetcher
    from .worldbank import WorldBankFetcher
    from .yahoo import YahooFetcher

    return {
        AlphaFetcher.SOURCE: AlphaFetcher,
        AlphaVantageFXFetcher.SOURCE: AlphaVantageFXFetcher,
        AQRFetcher.SOURCE: AQRFetcher,
        BinanceFetcher.SOURCE: BinanceFetcher,
        BISFetcher.SOURCE: BISFetcher,
        BOEFetcher.SOURCE: BOEFetcher,
        CBOEFetcher.SOURCE: CBOEFetcher,
        CoinGeckoFetcher.SOURCE: CoinGeckoFetcher,
        CurvoFetcher.SOURCE: CurvoFetcher,
        ECBFetcher.SOURCE: ECBFetcher,
        EODHDFetcher.SOURCE: EODHDFetcher,
        FREDFetcher.SOURCE: FREDFetcher,
        FrenchFetcher.SOURCE: FrenchFetcher,
        LBMAFetcher.SOURCE: LBMAFetcher,
        NareitFetcher.SOURCE: NareitFetcher,
        OECDFetcher.SOURCE: OECDFetcher,
        PortfolioVisualizerFetcher.SOURCE: PortfolioVisualizerFetcher,
        PortfolioChartsFetcher.SOURCE: PortfolioChartsFetcher,
        TestfolioPresetFetcher.SOURCE: TestfolioPresetFetcher,
        USMarketDataFetcher.SOURCE: USMarketDataFetcher,
        StooqFetcher.SOURCE: StooqFetcher,
        TiingoFetcher.SOURCE: TiingoFetcher,
        WorldBankFetcher.SOURCE: WorldBankFetcher,
        YahooFetcher.SOURCE: YahooFetcher,
    }


def available_sources() -> Sequence[str]:
    """Restituisce l'elenco alfabetico delle sorgenti disponibili per l'ingest."""

    return tuple(sorted(_fetcher_map().keys()))


def source_licenses() -> Mapping[str, str]:
    """Restituisce mappatura ``source -> license`` dichiarata dai fetcher."""

    mapping: dict[str, str] = {}
    for fetcher_cls in _fetcher_map().values():
        mapping[fetcher_cls.SOURCE] = fetcher_cls.LICENSE
    return mapping


def create_fetcher(source: str, **kwargs: object) -> BaseCSVFetcher:
    """Istanzia il fetcher corretto verificando che la sorgente sia supportata."""
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
    progress: bool = False,
) -> IngestArtifact:
    """Convenienza per eseguire l'ingest end-to-end senza toccare le classi.

    Args:
        source: Chiave della sorgente registrata (es. ``ecb``).
        symbols: Simboli opzionali da scaricare in override al default.
        start: Data minima per filtrare le osservazioni.
        raw_root: Cartella di destinazione per i CSV raw.
        as_of: Timestamp usato per etichettare gli artefatti.
        progress: Abilita la barra `tqdm` sui simboli scaricati.

    Returns:
        Artefatto risultante dallo scarico normalizzato.
    """
    fetcher = create_fetcher(source, raw_root=raw_root)
    return fetcher.fetch(symbols=symbols, start=start, as_of=as_of, progress=progress)
