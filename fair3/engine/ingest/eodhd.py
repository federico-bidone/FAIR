"""Fetcher per dati EOD Historical Data e backtes.to manuali."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final
from urllib.parse import urlencode

import pandas as pd
import requests

from .registry import BaseCSVFetcher

__all__ = ["EODHDFetcher"]


DEFAULT_SYMBOLS: Final[tuple[str, ...]] = ("SPY.US", "AGG.US")


class EODHDFetcher(BaseCSVFetcher):
    """Scarica serie mensili da EOD Historical Data con fallback manuale.

    Il fetcher supporta due modalità operative:

    * **Manuale:** se sotto ``manual_root`` è presente un CSV nominato come il
      simbolo richiesto (es. ``SPY.US.csv``) il file viene letto localmente. I
      file possono provenire da repository pubblici come
      `backtester-dani/backtests-to` che ridistribuisce estratti di
      EODHistoricalData fino al 2024.
    * **API:** in assenza del file locale, il fetcher utilizza l'endpoint
      `https://eodhistoricaldata.com/api/eod/<symbol>` con parametro
      ``period=m``. È necessario impostare ``EODHD_API_TOKEN`` o passare
      ``api_token`` al costruttore.

    Entrambe le modalità producono un DataFrame normalizzato con colonne
    ``date`` (``datetime64[ns]`` senza timezone), ``value`` (prezzo aggiustato o
    di chiusura) e ``symbol``.

    Attributes:
        manual_root: Directory contenente i CSV manuali.
        _api_token: Token API usato per l'accesso remoto, se disponibile.
        _period: Periodicità richiesta all'API (default mensile ``m``).
        _manual_overrides: Mappa dei simboli serviti da file manuali per
            consentire un parsing dedicato.
    """

    SOURCE = "eodhd"
    LICENSE = (
        "EOD Historical Data — commercial API; manual excerpts from backtes.to "
        "(educational use only)"
    )
    BASE_URL = "https://eodhistoricaldata.com/api/eod"
    DEFAULT_SYMBOLS = DEFAULT_SYMBOLS

    def __init__(
        self,
        *,
        manual_root: Path | str | None = None,
        api_token: str | None = None,
        period: str = "m",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.manual_root = Path(manual_root) if manual_root is not None else Path("data") / "eodhd"
        self._api_token = api_token or os.getenv("EODHD_API_TOKEN")
        self._period = period
        self._manual_overrides: dict[str, Path] = {}

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Costruisce l'URL API o il percorso manuale per il simbolo richiesto.

        Args:
            symbol: Codice EODHD (es. ``SPY.US``) o ticker equivalente.
            start: Data minima richiesta; se presente viene propagata al query
                parameter ``from`` per l'API.

        Returns:
            URL pronto per il download; per file locali utilizza lo schema
            ``manual://``.

        Raises:
            FileNotFoundError: Se il file manuale non esiste e non è disponibile
                un token API.
        """

        normalized_symbol = symbol.strip()
        manual_path = self._resolve_manual_path(normalized_symbol)
        if manual_path is not None:
            self._manual_overrides[normalized_symbol] = manual_path
            return f"manual://{manual_path}"

        self._manual_overrides.pop(normalized_symbol, None)
        if not self._api_token:
            msg = (
                "EODHD manual file not found and no API token configured. "
                "Populate data/eodhd with <symbol>.csv or set EODHD_API_TOKEN."
            )
            raise FileNotFoundError(msg)

        query: dict[str, str] = {
            "api_token": self._api_token,
            "period": self._period,
            "fmt": "json",
        }
        if start is not None:
            query["from"] = pd.Timestamp(start).date().isoformat()
        return f"{self.BASE_URL}/{normalized_symbol}?{urlencode(query)}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Interpreta la risposta EODHD in un DataFrame canonico FAIR.

        Args:
            payload: Stringa restituita da :meth:`_download`.
            symbol: Simbolo originariamente richiesto.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol`` ordinate per
            data.

        Raises:
            ValueError: Se il payload contiene HTML (rate limit o errore) o non
                espone le colonne richieste.
        """

        normalized_symbol = symbol.strip()
        stripped = payload.lstrip()
        if stripped.startswith("<"):
            msg = "EODHD returned HTML payload; check API token, license status, or rate limits."
            raise ValueError(msg)

        if normalized_symbol in self._manual_overrides:
            manual_path = self._manual_overrides[normalized_symbol]
            return self._parse_manual_csv(manual_path, normalized_symbol)

        try:
            parsed = json.loads(stripped or "[]")
        except json.JSONDecodeError as exc:  # pragma: no cover - difesa
            msg = "Unable to decode EODHD JSON payload."
            raise ValueError(msg) from exc

        if isinstance(parsed, dict):
            error_message = parsed.get("error") or parsed.get("message")
            if error_message:
                raise ValueError(f"EODHD error: {error_message}")
            data_payload = parsed.get("data")
        else:
            data_payload = parsed

        if not isinstance(data_payload, list):
            raise ValueError("EODHD payload must be a list of observations")
        if not data_payload:
            return pd.DataFrame({"date": [], "value": [], "symbol": []})

        frame = pd.DataFrame(data_payload)
        return self._normalize_table(frame, normalized_symbol)

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        """Scarica i contenuti gestendo lo schema manuale personalizzato.

        Args:
            url: URL o percorso ``manual://`` generato da :meth:`build_url`.
            session: Sessione HTTP opzionale per richieste API.

        Returns:
            Contenuto testuale del file locale o della risposta HTTP.

        Raises:
            FileNotFoundError: Se il file manuale non è presente.
        """

        if url.startswith("manual://"):
            manual_path = Path(url.replace("manual://", "", 1))
            if not manual_path.exists():
                raise FileNotFoundError(f"Manual EODHD file missing: {manual_path}")
            return manual_path.read_text(encoding="utf-8")
        return super()._download(url, session=session)

    def _resolve_manual_path(self, symbol: str) -> Path | None:
        """Restituisce il percorso CSV manuale se disponibile.

        Args:
            symbol: Simbolo richiesto dal fetcher.

        Returns:
            Percorso al file CSV oppure ``None`` se non trovato.
        """

        candidates = [
            self.manual_root / f"{symbol}.csv",
            self.manual_root / f"{symbol.upper()}.csv",
            self.manual_root / f"{symbol.lower()}.csv",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _parse_manual_csv(self, path: Path, symbol: str) -> pd.DataFrame:
        """Legge un CSV manuale e restituisce la serie normalizzata.

        Args:
            path: Percorso del file salvato dall'utente.
            symbol: Simbolo di output assegnato alla serie.

        Returns:
            DataFrame con schema FAIR.
        """

        frame = pd.read_csv(path)
        return self._normalize_table(frame, symbol)

    def _normalize_table(self, table: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Converte una tabella EODHD in ``date``/``value``/``symbol``.

        Args:
            table: DataFrame sorgente contenente almeno ``date`` o ``Date``.
            symbol: Simbolo normalizzato per il risultato.

        Returns:
            DataFrame pronto per l'ETL con colonne ordinate.

        Raises:
            ValueError: Se non sono presenti colonne data/valore compatibili.
        """

        date_column = self._first_column(
            table,
            candidates=("date", "Date", "DATE"),
            kind="date",
        )
        value_column = self._first_column(
            table,
            candidates=(
                "adjusted_close",
                "Adjusted_close",
                "Adjusted Close",
                "Adj Close",
                "close",
                "Close",
            ),
            kind="value",
        )
        dates = pd.to_datetime(table[date_column], errors="coerce", utc=True)
        values = pd.to_numeric(table[value_column], errors="coerce")
        if values.isna().any():
            alt_column = None
            if value_column.lower() != "close":
                if "close" in table.columns:
                    alt_column = "close"
                elif "Close" in table.columns:
                    alt_column = "Close"
            if alt_column:
                alt_values = pd.to_numeric(table[alt_column], errors="coerce")
                values = values.fillna(alt_values)
        frame = pd.DataFrame(
            {
                "date": dates.dt.tz_convert(None),
                "value": values,
                "symbol": symbol,
            }
        )
        frame = frame.dropna(subset=["date", "value"]).reset_index(drop=True)
        return frame

    @staticmethod
    def _first_column(
        table: pd.DataFrame,
        *,
        candidates: tuple[str, ...],
        kind: str,
    ) -> str:
        """Trova la prima colonna disponibile tra quelle candidate.

        Args:
            table: DataFrame da ispezionare.
            candidates: Sequenza di nomi possibili.
            kind: Etichetta usata nel messaggio di errore.

        Returns:
            Nome della colonna trovata.

        Raises:
            ValueError: Se nessuna colonna candidata è presente.
        """

        for column in candidates:
            if column in table.columns:
                return column
        available = ", ".join(table.columns.astype(str))
        raise ValueError(
            f"EODHD payload missing {kind} column; searched {candidates}, available {available}"
        )
