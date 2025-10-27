"""Fetcher manuale per le serie di riferimento Portfolio Visualizer."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import MonthEnd

from .registry import BaseCSVFetcher


@dataclass(frozen=True)
class PortfolioVisualizerDataset:
    """Descrive un dataset Portfolio Visualizer disponibile tramite drop manuale.

    Attributes:
        filename: Nome del file CSV atteso sotto ``manual_root``.
        date_column: Colonna con la data di riferimento nel file sorgente.
        value_column: Colonna contenente il valore o il rendimento.
        scale: Fattore moltiplicativo da applicare ai valori (es. 0.01 per percentuali).
        frequency: Frequenza attesa dei dati (``monthly`` o ``daily``).
        rename: Nome simbolo opzionale da usare nell'output al posto del simbolo richiesto.
    """

    filename: str
    date_column: str = "Date"
    value_column: str = "Return"
    scale: float = 1.0
    frequency: str = "monthly"
    rename: str | None = None


DATASETS: Mapping[str, PortfolioVisualizerDataset] = {
    "us_total_stock_market": PortfolioVisualizerDataset(
        filename="US_Total_Stock_Market.csv",
        scale=0.01,
    ),
    "international_developed_market": PortfolioVisualizerDataset(
        filename="International_Developed_Market.csv",
        scale=0.01,
    ),
    "us_total_bond_market": PortfolioVisualizerDataset(
        filename="US_Total_Bond_Market.csv",
        scale=0.01,
    ),
    "gold_total_return": PortfolioVisualizerDataset(
        filename="Gold_Total_Return.csv",
        scale=0.01,
    ),
}


class PortfolioVisualizerFetcher(BaseCSVFetcher):
    """Fetcher manuale per i dataset mensili scaricati da Portfolio Visualizer."""

    SOURCE = "portviz"
    LICENSE = "Portfolio Visualizer — informational/educational use"
    BASE_URL = "https://www.portfoliovisualizer.com"
    DEFAULT_SYMBOLS = tuple(DATASETS.keys())

    def __init__(
        self,
        *,
        manual_root: Path | str | None = None,
        raw_root: Path | str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(raw_root=raw_root, **kwargs)
        if manual_root is not None:
            self.manual_root = Path(manual_root)
        else:
            base_manual = Path("data") / "portfolio_visualizer_manual"
            self.manual_root = base_manual

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce il percorso al file manuale per il dataset richiesto.

        Args:
            symbol: Identificatore interno del dataset Portfolio Visualizer.
            start: Timestamp minimo richiesto (ignorato, presente per compatibilità).

        Returns:
            Percorso con schema ``manual://`` da cui leggere il CSV.

        Raises:
            FileNotFoundError: Se il file manuale non è presente nella directory attesa.
        """

        spec = self._dataset_spec(symbol)
        manual_path = self.manual_root / spec.filename
        if not manual_path.exists():
            msg = (
                "Manual Portfolio Visualizer dataset missing. Download it via the website "
                f"and place it under {manual_path}."
            )
            raise FileNotFoundError(msg)
        return f"manual://{manual_path}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il CSV Portfolio Visualizer in DataFrame FAIR standard.

        Args:
            payload: Contenuto testuale del file CSV.
            symbol: Identificatore del dataset richiesto.

        Returns:
            DataFrame normalizzato con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se il payload appare HTML o mancano le colonne attese.
        """

        if payload.lstrip().startswith("<"):
            msg = "Unexpected HTML payload for Portfolio Visualizer dataset; check download steps."
            raise ValueError(msg)
        spec = self._dataset_spec(symbol)
        frame = pd.read_csv(StringIO(payload))
        if spec.date_column not in frame.columns or spec.value_column not in frame.columns:
            msg = (
                "Missing expected columns in Portfolio Visualizer dataset: "
                f"{spec.date_column}/{spec.value_column}"
            )
            raise ValueError(msg)
        dates = pd.to_datetime(frame[spec.date_column], errors="coerce")
        if spec.frequency == "monthly":
            dates = dates + MonthEnd(0)
        values = pd.to_numeric(frame[spec.value_column], errors="coerce") * spec.scale
        symbol_name = spec.rename or symbol
        result = pd.DataFrame({"date": dates, "value": values, "symbol": symbol_name})
        result = result.dropna(subset=["date", "value"]).reset_index(drop=True)
        return result

    def _dataset_spec(self, symbol: str) -> PortfolioVisualizerDataset:
        """Recupera i metadati dichiarativi del dataset richiesto.

        Args:
            symbol: Nome interno del dataset Portfolio Visualizer.

        Returns:
            Configurazione dichiarativa usata per parsing e validazione.

        Raises:
            ValueError: Se il dataset richiesto non è supportato.
        """

        try:
            return DATASETS[symbol]
        except KeyError as exc:  # pragma: no cover - difensivo
            raise ValueError(f"Unsupported Portfolio Visualizer dataset: {symbol}") from exc

    def _download(self, url: str, *, session: object | None = None) -> str:
        """Legge il file manuale da disco restituendo il contenuto testuale.

        Args:
            url: Percorso sorgente (``manual://`` o HTTP) da scaricare.
            session: Sessione HTTP opzionale (ignorata per percorsi manuali).

        Returns:
            Contenuto testuale del file.

        Raises:
            FileNotFoundError: Se il percorso manuale indicato non esiste.
        """

        if url.startswith("manual://"):
            manual_path = Path(url.replace("manual://", ""))
            if not manual_path.exists():
                raise FileNotFoundError(f"Manual dataset not found: {manual_path}")
            return manual_path.read_text(encoding="utf-8")
        return super()._download(url, session=session)
