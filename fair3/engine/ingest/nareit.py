"""Fetcher manuale per le serie FTSE Nareit mensili."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import MonthEnd

from .registry import BaseCSVFetcher


@dataclass(frozen=True)
class SeriesSpec:
    """Metadati dichiarativi per una serie Nareit supportata.

    Attributes:
        filename: Nome del file Excel che deve essere posizionato nella directory
            manuale.
        sheet_name: Nome del foglio Excel da cui leggere i dati.
        date_column: Colonna che contiene la data di riferimento della serie.
        value_column: Colonna che contiene il valore della serie.
        frequency: Frequenza temporale della serie (``monthly`` o ``quarterly``).
        scale: Fattore moltiplicativo da applicare al valore grezzo (es. 0.01 per
            convertire percentuali in decimali).
    """

    filename: str
    sheet_name: str
    date_column: str
    value_column: str
    frequency: str = "monthly"
    scale: float = 1.0


SERIES: Mapping[str, SeriesSpec] = {
    "all_equity_reit_tr": SeriesSpec(
        filename="NAREIT_AllSeries.xlsx",
        sheet_name="Monthly",
        date_column="Date",
        value_column="All Equity REITs Total Return",
    ),
    "mreit_tr": SeriesSpec(
        filename="NAREIT_AllSeries.xlsx",
        sheet_name="Monthly",
        date_column="Date",
        value_column="Mortgage REITs Total Return",
    ),
}


class NareitFetcher(BaseCSVFetcher):
    """Scarica file Excel Nareit presenti localmente e li normalizza."""

    SOURCE = "nareit"
    LICENSE = "FTSE Nareit data — informational use only"
    BASE_URL = "https://www.reit.com/data-research/data"  # riferimento informativo
    DEFAULT_SYMBOLS = tuple(SERIES.keys())

    def __init__(
        self,
        *,
        manual_root: Path | str | None = None,
        raw_root: Path | str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(raw_root=raw_root, **kwargs)
        self.manual_root = (
            Path(manual_root) if manual_root is not None else Path("data") / "nareit_manual"
        )

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce il percorso locale del file Excel per la serie richiesta.

        Args:
            symbol: Identificatore della serie Nareit (es. ``all_equity_reit_tr``).
            start: Timestamp minimo richiesto (ignorato; la frequenza è mensile).

        Returns:
            Percorso in formato ``manual://`` che verrà letto da ``_download``.

        Raises:
            FileNotFoundError: Se il file Excel non è presente nella directory
                manuale configurata.
        """

        spec = self._series_spec(symbol)
        manual_path = self.manual_root / spec.filename
        if not manual_path.exists():
            msg = (
                f"File Nareit mancante. Scarica l'Excel dal sito Nareit e copialo in {manual_path}."
            )
            raise FileNotFoundError(msg)
        return f"manual://{manual_path}"

    def parse(self, payload: bytes | str, symbol: str) -> pd.DataFrame:
        """Converte il payload Excel in un DataFrame canonico FAIR.

        Args:
            payload: Contenuto binario del file Excel scaricato.
            symbol: Nome della serie richiesta.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se vengono riscontrati payload HTML o colonne mancanti.
        """

        if isinstance(payload, str):
            if payload.lstrip().startswith("<"):
                msg = "Nareit: payload HTML ricevuto, controllare la sorgente manuale."
                raise ValueError(msg)
            buffer = BytesIO(payload.encode("utf-8"))
        else:
            if payload.startswith(b"<"):
                msg = "Nareit: payload HTML ricevuto, controllare la sorgente manuale."
                raise ValueError(msg)
            buffer = BytesIO(payload)

        spec = self._series_spec(symbol)
        frame = pd.read_excel(buffer, sheet_name=spec.sheet_name)
        if spec.date_column not in frame.columns or spec.value_column not in frame.columns:
            msg = f"Colonne attese mancanti nel file Nareit: {spec.date_column}/{spec.value_column}"
            raise ValueError(msg)

        dates = pd.to_datetime(frame[spec.date_column], errors="coerce")
        if spec.frequency == "monthly":
            dates = dates + MonthEnd(0)
        values = pd.to_numeric(frame[spec.value_column], errors="coerce") * spec.scale
        result = pd.DataFrame({"date": dates, "value": values, "symbol": symbol})
        result = result.dropna(subset=["date", "value"]).reset_index(drop=True)
        return result

    def _download(
        self,
        url: str,
        *,
        session: object | None = None,
    ) -> bytes:
        """Legge i file manuali dal disco senza usare HTTP."""

        if url.startswith("manual://"):
            manual_path = Path(url.replace("manual://", ""))
            return manual_path.read_bytes()
        payload = super()._download(url, session=session)
        return payload.encode("utf-8")

    def _series_spec(self, symbol: str) -> SeriesSpec:
        """Recupera la configurazione dichiarativa per il simbolo richiesto."""

        try:
            return SERIES[symbol]
        except KeyError as exc:  # pragma: no cover - difensivo
            raise ValueError(f"Serie Nareit non supportata: {symbol}") from exc
