# ruff: noqa: F404

"""Fetcher manuale o HTTP per i dataset AQR."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from pandas.tseries.offsets import MonthEnd

from .registry import BaseCSVFetcher


@dataclass(frozen=True)
class DatasetSpec:
    """Descrive la struttura di un dataset AQR supportato.

    Attributes:
        filename: Nome del file locale previsto sotto ``manual_root``.
        date_column: Colonna con la data nel file sorgente.
        value_column: Colonna con il valore del fattore.
        scale: Fattore moltiplicativo (es. 0.01 per percentuali).
        date_format: Formato esplicito da usare con ``pd.to_datetime``.
        frequency: Frequenza attesa (``monthly`` o ``daily``).
        url: URL HTTP opzionale se il dataset è scaricabile direttamente.
    """

    filename: str
    date_column: str
    value_column: str
    scale: float = 1.0
    date_format: str | None = None
    frequency: str = "monthly"
    url: str | None = None


DATASETS: Mapping[str, DatasetSpec] = {
    "qmj_us": DatasetSpec(
        filename="QMJ_US.csv",
        date_column="Date",
        value_column="QMJ",
        scale=0.01,
    ),
    "bab_us": DatasetSpec(
        filename="BAB_US.csv",
        date_column="Date",
        value_column="BAB",
        scale=0.01,
    ),
    "value_global": DatasetSpec(
        filename="VALUE_Global.csv",
        date_column="Date",
        value_column="VALUE",
        scale=0.01,
    ),
}


class AQRFetcher(BaseCSVFetcher):
    """Ingestor per i dataset AQR con fallback manuale e parsing deterministico.

    Attributes:
        manual_root: Directory che ospita i file scaricati manualmente.
    """

    SOURCE = "aqr"
    LICENSE = "AQR Data Sets — for educational use only"
    BASE_URL = "https://www.aqr.com"
    DEFAULT_SYMBOLS = tuple(DATASETS.keys())

    def __init__(
        self,
        *,
        manual_root: Path | str | None = None,
        raw_root: Path | str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(raw_root=raw_root, **kwargs)
        self.manual_root = (
            Path(manual_root) if manual_root is not None else Path("data") / "aqr_manual"
        )

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce il percorso sorgente per il dataset richiesto.

        Args:
            symbol: Identificatore del dataset supportato (es. ``qmj_us``).
            start: Timestamp minimo richiesto (ignorato dai dataset AQR).

        Returns:
            Stringa che rappresenta l'origine del file (``manual://`` o URL HTTP).

        Raises:
            FileNotFoundError: Se il file manuale non è presente nel percorso atteso.
        """

        spec = self._dataset_spec(symbol)
        if spec.url:
            return spec.url
        manual_path = self.manual_root / spec.filename
        if not manual_path.exists():
            msg = f"Manual dataset missing. Download it from AQR and place it under {manual_path}."
            raise FileNotFoundError(msg)
        return f"manual://{manual_path}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il payload CSV AQR in un DataFrame canonico FAIR.

        Args:
            payload: Contenuto testuale del file CSV.
            symbol: Nome del dataset richiesto.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se il payload appare HTML o mancano le colonne attese.
        """

        if payload.lstrip().startswith("<"):
            msg = "Unexpected HTML payload received for AQR dataset; check login or rate limits."
            raise ValueError(msg)
        spec = self._dataset_spec(symbol)
        frame = pd.read_csv(StringIO(payload))
        if spec.date_column not in frame.columns or spec.value_column not in frame.columns:
            msg = f"Missing expected columns in AQR dataset: {spec.date_column}/{spec.value_column}"
            raise ValueError(msg)
        if spec.date_format:
            dates = pd.to_datetime(
                frame[spec.date_column].astype(str),
                format=spec.date_format,
                errors="coerce",
            )
        else:
            dates = pd.to_datetime(frame[spec.date_column], errors="coerce")
        if spec.frequency == "monthly":
            dates = dates + MonthEnd(0)
        values = pd.to_numeric(frame[spec.value_column], errors="coerce") * spec.scale
        result = pd.DataFrame(
            {
                "date": dates,
                "value": values,
                "symbol": symbol,
            }
        )
        result = result.dropna(subset=["date", "value"]).reset_index(drop=True)
        return result

    def _dataset_spec(self, symbol: str) -> DatasetSpec:
        """Restituisce la configurazione dichiarativa del dataset richiesto.

        Args:
            symbol: Nome interno del dataset AQR.

        Returns:
            Metadati dichiarativi necessari al parsing.

        Raises:
            ValueError: Se il dataset non è supportato.
        """

        try:
            return DATASETS[symbol]
        except KeyError as exc:  # pragma: no cover - difensivo
            raise ValueError(f"Unsupported AQR dataset: {symbol}") from exc

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        """Scarica dati gestendo sia HTTP che file manuali.

        Args:
            url: Origine del file (``manual://`` o URL HTTP).
            session: Sessione ``requests`` opzionale da riutilizzare.

        Returns:
            Payload testuale pronto per il parsing.

        Raises:
            FileNotFoundError: Se il percorso manuale non esiste.
        """

        if url.startswith("manual://"):
            manual_path = Path(url.replace("manual://", ""))
            if not manual_path.exists():
                msg = (
                    "Manual dataset missing. Download it from AQR and place it under "
                    f"{manual_path}."
                )
                raise FileNotFoundError(msg)
            return manual_path.read_text(encoding="utf-8")
        return super()._download(url, session=session)
