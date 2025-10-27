"""Fetcher per dataset Alpha Architect, q-Factors e Novy-Marx."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from pandas.tseries.offsets import MonthEnd

from .registry import BaseCSVFetcher


@dataclass(frozen=True)
class AlphaDatasetSpec:
    """Metadati dichiarativi per un dataset Alpha/q-Factors/Novy-Marx.

    Attributes:
        value_column: Nome della colonna contenente il valore del fattore.
        date_column: Nome della colonna con la data.
        frequency: Frequenza dichiarata del dataset (``monthly`` o ``daily``).
        scale: Fattore moltiplicativo da applicare ai valori (es. 0.01 per %).
        url: URL HTTP da cui scaricare il dataset, se disponibile.
        manual_filename: Nome del file locale se il download richiede intervento manuale.
        fmt: Formato atteso del payload (``csv`` o ``html_table``).
        table_index: Indice della tabella HTML da utilizzare quando ``fmt`` è ``html_table``.
    """

    value_column: str
    date_column: str = "Date"
    frequency: str = "monthly"
    scale: float = 1.0
    url: str | None = None
    manual_filename: str | None = None
    fmt: str = "csv"
    table_index: int = 0


DATASETS: dict[str, AlphaDatasetSpec] = {
    "alpha_qmj": AlphaDatasetSpec(
        url="https://alphaarchitect.com/strategies/qmj.csv",
        value_column="QMJ",
        scale=0.01,
    ),
    "qfactors_roe": AlphaDatasetSpec(
        url="https://global-q.org/downloads/q5_factors_monthly.csv",
        value_column="ROE",
        scale=0.01,
    ),
    "novy_profitability": AlphaDatasetSpec(
        manual_filename="NovyMarx_Profitability.html",
        value_column="Profitability",
        fmt="html_table",
        table_index=0,
        scale=0.01,
    ),
}


class AlphaFetcher(BaseCSVFetcher):
    """Fetcher per dataset Alpha Architect, q-Factors e Novy-Marx."""

    SOURCE = "alpha"
    LICENSE = "Alpha Architect / q-Factors / Novy-Marx — educational use only"
    BASE_URL = "https://alphaarchitect.com"
    DEFAULT_SYMBOLS = tuple(DATASETS.keys())

    def __init__(self, *, manual_root: Path | str | None = None, **kwargs: object) -> None:
        """Inizializza il fetcher con percorso manuale opzionale.

        Args:
            manual_root: Directory che ospita i file scaricati manualmente.
            **kwargs: Parametri addizionali inoltrati alla superclasse.
        """

        super().__init__(**kwargs)
        self.manual_root = (
            Path(manual_root) if manual_root is not None else Path("data") / "alpha_manual"
        )

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce l'URL o il percorso manuale associato al dataset richiesto.

        Args:
            symbol: Identificatore interno del dataset.
            start: Timestamp minimo richiesto (ignorato in questa integrazione).

        Returns:
            Stringa che rappresenta l'origine del dataset (HTTP o ``manual://``).

        Raises:
            FileNotFoundError: Se il dataset richiede un file manuale assente.
            ValueError: Se la configurazione del dataset non specifica alcuna sorgente.
        """

        del start  # Il parametro è previsto dalla firma ma non utilizzato dai dataset.
        spec = self._dataset_spec(symbol)
        if spec.url:
            return spec.url
        if spec.manual_filename is None:
            msg = f"Dataset {symbol} lacks both URL and manual filename"
            raise ValueError(msg)
        manual_path = self.manual_root / spec.manual_filename
        if not manual_path.exists():
            msg = (
                "Manual dataset missing. Download it from the provider and place it under "
                f"{manual_path}."
            )
            raise FileNotFoundError(msg)
        return f"manual://{manual_path}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il payload in DataFrame canonicalizzato con colonne FAIR.

        Args:
            payload: Contenuto testuale del dataset.
            symbol: Identificatore interno richiesto.

        Returns:
            DataFrame con colonne ``date``, ``value`` e ``symbol``.

        Raises:
            ValueError: Se il payload ha formato inatteso o mancano colonne necessarie.
        """

        spec = self._dataset_spec(symbol)
        if spec.fmt == "csv":
            if payload.lstrip().startswith("<"):
                msg = "Unexpected HTML payload received for alpha dataset"
                raise ValueError(msg)
            frame = pd.read_csv(StringIO(payload))
        elif spec.fmt == "html_table":
            frame = self._parse_html_table(payload, spec.table_index)
        else:
            msg = f"Unsupported dataset format: {spec.fmt}"
            raise ValueError(msg)
        if spec.date_column not in frame.columns or spec.value_column not in frame.columns:
            msg = "Missing expected columns in alpha dataset payload"
            raise ValueError(msg)
        dates = pd.to_datetime(frame[spec.date_column], errors="coerce")
        if spec.frequency == "monthly":
            dates = dates + MonthEnd(0)
        values = pd.to_numeric(frame[spec.value_column], errors="coerce") * spec.scale
        result = pd.DataFrame({"date": dates, "value": values, "symbol": symbol})
        return result.dropna(subset=["date", "value"]).reset_index(drop=True)

    def _dataset_spec(self, symbol: str) -> AlphaDatasetSpec:
        """Recupera i metadati dichiarativi per il dataset richiesto.

        Args:
            symbol: Identificatore interno del dataset.

        Returns:
            Oggetto ``AlphaDatasetSpec`` con informazioni di parsing.

        Raises:
            ValueError: Se il dataset non è supportato.
        """

        try:
            return DATASETS[symbol]
        except KeyError as exc:  # pragma: no cover - difensivo
            msg = f"Unsupported alpha dataset: {symbol}"
            raise ValueError(msg) from exc

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> str:
        """Scarica il payload gestendo percorsi manuali e HTTP standard.

        Args:
            url: Sorgente del dataset (``manual://`` o URL HTTP).
            session: Sessione ``requests`` riutilizzabile.

        Returns:
            Contenuto testuale del dataset.

        Raises:
            FileNotFoundError: Se il file manuale atteso non è disponibile.
        """

        if url.startswith("manual://"):
            manual_path = Path(url.replace("manual://", ""))
            if not manual_path.exists():
                msg = (
                    "Manual dataset missing. Download it from the provider and place it under "
                    f"{manual_path}."
                )
                raise FileNotFoundError(msg)
            return manual_path.read_text(encoding="utf-8")
        return super()._download(url, session=session)

    def _parse_html_table(self, payload: str, table_index: int) -> pd.DataFrame:
        """Analizza una tabella HTML minima senza dipendenze opzionali.

        Args:
            payload: Contenuto HTML dell'intero documento.
            table_index: Indice della tabella da selezionare (0-based).

        Returns:
            DataFrame costruito a partire dalle celle della tabella.

        Raises:
            ValueError: Se non viene trovata alcuna tabella o l'indice richiesto è fuori range.
        """

        parser = _SimpleHTMLTableParser()
        parser.feed(payload)
        parser.close()
        tables = parser.tables
        if not tables or table_index >= len(tables):
            msg = "Expected HTML table was not found in payload"
            raise ValueError(msg)
        rows = tables[table_index]
        if not rows:
            msg = "HTML table contains no rows"
            raise ValueError(msg)
        header: Sequence[str] | None = None
        data_rows: list[list[str]]
        if len(rows) > 1 and len(rows[0]) == len(rows[1]):
            header = rows[0]
            data_rows = rows[1:]
        else:
            data_rows = rows
        frame = pd.DataFrame(data_rows, columns=header)
        return frame


class _SimpleHTMLTableParser(HTMLParser):
    """Parser HTML minimale che estrae celle da tabelle in forma di lista."""

    def __init__(self) -> None:
        super().__init__()
        self._tables: list[list[list[str]]] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] = []
        self._in_cell = False

    @property
    def tables(self) -> list[list[list[str]]]:
        """Restituisce le tabelle parse come liste di righe e celle."""

        return self._tables

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._current_table = []
        elif tag == "tr":
            self._current_row = []
        elif tag in {"td", "th"}:
            self._in_cell = True
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            stripped = data.strip()
            if stripped:
                self._current_cell.append(stripped)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._current_row is not None:
            cell_text = " ".join(self._current_cell).strip()
            self._current_row.append(cell_text)
            self._in_cell = False
        elif tag == "tr" and self._current_table is not None and self._current_row:
            self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == "table" and self._current_table is not None:
            if self._current_row:
                self._current_table.append(self._current_row)
                self._current_row = None
            if self._current_table:
                self._tables.append(self._current_table)
            self._current_table = None
