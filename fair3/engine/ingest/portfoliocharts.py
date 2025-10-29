"""Parser e fetcher manuale per i dataset PortfolioCharts (Simba)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Final

import pandas as pd
from pandas.tseries.offsets import MonthEnd

from .registry import BaseCSVFetcher, IngestArtifact

__all__ = ["parse_portfoliocharts_simba", "PortfolioChartsFetcher"]


DEFAULT_SHEET_COLUMN_MAPPING: Final[dict[str, dict[str, str]]] = {
    "Data_Series": {
        "US Large Cap": "US_LARGE_CAP",
        "US Mid Cap": "US_MID_CAP",
        "US Small Cap": "US_SMALL_CAP",
        "International Stocks": "INTL_DEVELOPED_EQ",
        "Emerging Markets": "EM_EQ",
        "US Bonds": "US_TOTAL_BOND",
        "International Bonds": "INTL_TOTAL_BOND",
    },
    "Stocks": {
        "Large Cap Value": "US_LARGE_VALUE",
        "Large Cap Growth": "US_LARGE_GROWTH",
        "Small Cap Value": "US_SMALL_VALUE",
        "Small Cap Growth": "US_SMALL_GROWTH",
    },
}

SIMBA_DEFAULT_SYMBOLS: Final[tuple[str, ...]] = tuple(
    sorted({
        symbol
        for column_map in DEFAULT_SHEET_COLUMN_MAPPING.values()
        for symbol in column_map.values()
    })
)

DEFAULT_WORKBOOK_NAME: Final[str] = "PortfolioCharts_Simba.xlsx"


def parse_portfoliocharts_simba(
    xlsx_path: Path,
    *,
    mapping: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:
    """Estrae le serie rilevanti dal file Simba di PortfolioCharts.

    Args:
        xlsx_path: Percorso al file Excel ``Simba`` scaricato manualmente.
        mapping: Mappa opzionale ``{foglio: {colonna_excel: simbolo_interno}}``.

    Returns:
        Una tupla contenente il DataFrame normalizzato (colonne ``date``, ``value``,
        ``symbol``) e un dizionario con metadati per ogni simbolo (`sheet`,
        `column`). Le date sono convertite a fine mese (timezone naive) per
        rispettare l'allineamento mensile del workbook.

    Raises:
        FileNotFoundError: Se ``xlsx_path`` non esiste.
        ValueError: Se un foglio non è presente o manca la colonna data.
    """

    if not xlsx_path.exists():
        msg = (
            "PortfolioCharts Simba workbook not found. "
            f"Expected file at {xlsx_path}."
        )
        raise FileNotFoundError(msg)
    column_mapping = mapping or DEFAULT_SHEET_COLUMN_MAPPING
    frames: list[pd.DataFrame] = []
    symbol_metadata: dict[str, dict[str, str]] = {}

    with pd.ExcelFile(xlsx_path) as workbook:
        for sheet_name, sheet_map in column_mapping.items():
            try:
                sheet_df = workbook.parse(sheet_name)
            except ValueError as exc:  # pragma: no cover - defensive
                msg = f"Sheet '{sheet_name}' not found in PortfolioCharts workbook"
                raise ValueError(msg) from exc

            date_column = None
            for candidate in ("Date", "date", "DATE"):
                if candidate in sheet_df.columns:
                    date_column = candidate
                    break
            if date_column is None:
                msg = (
                    f"Sheet '{sheet_name}' must include a 'Date' column to parse "
                    "PortfolioCharts Simba data"
                )
                raise ValueError(msg)

            required_columns = set(sheet_map.keys())
            missing_columns = required_columns.difference(sheet_df.columns)
            if missing_columns:
                missing_fmt = ", ".join(sorted(missing_columns))
                msg = (
                    f"Sheet '{sheet_name}' is missing expected columns: {missing_fmt}"
                )
                raise ValueError(msg)

            subset = sheet_df[[date_column, *sheet_map.keys()]].copy()
            subset = subset.rename(columns={date_column: "date"})
            subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
            subset = subset.dropna(subset=["date"])
            subset["date"] = subset["date"] + MonthEnd(0)
            rename_map = {excel_col: symbol for excel_col, symbol in sheet_map.items()}
            subset = subset.rename(columns=rename_map)
            tidy = subset.melt(
                id_vars="date",
                value_vars=list(rename_map.values()),
                var_name="symbol",
                value_name="value",
            )
            tidy["value"] = pd.to_numeric(tidy["value"], errors="coerce")
            tidy = tidy.dropna(subset=["value"])
            frames.append(tidy)

            for excel_col, symbol in sheet_map.items():
                symbol_metadata[symbol] = {
                    "sheet": sheet_name,
                    "column": excel_col,
                }

    if frames:
        data = pd.concat(frames, ignore_index=True)
    else:  # pragma: no cover - empty workbook is exceptional
        data = pd.DataFrame(columns=["date", "symbol", "value"])
    data = data.sort_values(["symbol", "date"]).reset_index(drop=True)
    return data, symbol_metadata


class PortfolioChartsFetcher(BaseCSVFetcher):
    """Fetcher manuale per la Simba Backtesting Spreadsheet di PortfolioCharts."""

    SOURCE = "portfoliocharts"
    LICENSE = (
        "PortfolioCharts Simba Backtesting Spreadsheet — informational/educational use"
    )
    BASE_URL = (
        "https://portfoliocharts.com/portfolio/portfolio-charts-simba-backtesting-spreadsheet"
    )
    DEFAULT_SYMBOLS: Final[tuple[str, ...]] = SIMBA_DEFAULT_SYMBOLS
    __test__ = False

    def __init__(
        self,
        *,
        manual_root: Path | str | None = None,
        workbook_name: str = DEFAULT_WORKBOOK_NAME,
        sheet_mapping: Mapping[str, Mapping[str, str]] | None = None,
        raw_root: Path | str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(raw_root=raw_root, **kwargs)
        self.manual_root = (
            Path(manual_root) if manual_root is not None else Path("data") / "portfoliocharts"
        )
        self.workbook_name = workbook_name
        self.sheet_mapping = sheet_mapping or DEFAULT_SHEET_COLUMN_MAPPING

    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: date | datetime | None = None,
        as_of: datetime | None = None,
        progress: bool = False,
        session: object | None = None,
    ) -> IngestArtifact:
        """Carica le serie PortfolioCharts richieste dal workbook manuale.

        Args:
            symbols: Lista di simboli interni (es. ``US_LARGE_CAP``). Se omessa,
                vengono restituiti tutti i simboli noti.
            start: Data minima (inclusiva) per filtrare le osservazioni.
            as_of: Timestamp usato per etichettare l'artefatto generato.
            progress: Argomento compatibile con la superclasse; ignorato.
            session: Argomento compatibile con la superclasse; ignorato.

        Returns:
            Artefatto di ingest con dati normalizzati e metadati di audit.

        Raises:
            FileNotFoundError: Se il workbook manuale è assente.
            ValueError: Se viene richiesto un simbolo sconosciuto o la lista è vuota.
        """

        del progress, session  # pragma: no cover - compatibilità firma
        workbook_path = self.manual_root / self.workbook_name
        data, metadata_map = parse_portfoliocharts_simba(
            workbook_path,
            mapping=self.sheet_mapping,
        )
        available_symbols = set(metadata_map.keys())

        if symbols is None:
            requested = sorted(available_symbols)
        else:
            requested = [str(symbol) for symbol in symbols]
        if not requested:
            raise ValueError("At least one symbol must be provided")

        unknown = [symbol for symbol in requested if symbol not in available_symbols]
        if unknown:
            missing_fmt = ", ".join(sorted(unknown))
            raise ValueError(f"Unknown PortfolioCharts symbols: {missing_fmt}")

        timestamp = as_of or datetime.now(UTC)
        start_ts = pd.to_datetime(start) if start is not None else None
        frames: list[pd.DataFrame] = []
        requests_meta: list[MutableMapping[str, Any]] = []

        for symbol in requested:
            frame = data[data["symbol"] == symbol].copy()
            if start_ts is not None:
                frame = frame[frame["date"] >= start_ts]
            frame = frame.sort_values("date").reset_index(drop=True)
            frames.append(frame)
            mapping_info = metadata_map.get(symbol, {})
            requests_meta.append(
                {
                    "symbol": symbol,
                    "workbook": str(workbook_path),
                    "sheet": mapping_info.get("sheet"),
                    "column": mapping_info.get("column"),
                    "rows": len(frame),
                }
            )
            self.logger.info(
                "ingest_complete source=%s symbol=%s rows=%d license=%s workbook=%s",
                self.SOURCE,
                symbol,
                len(frame),
                self.LICENSE,
                workbook_path,
            )

        if frames:
            combined = pd.concat(frames, ignore_index=True)
        else:  # pragma: no cover - richiesto per tipizzazione
            combined = pd.DataFrame(columns=["date", "symbol", "value"])

        path = self._write_csv(combined, timestamp)
        metadata: MutableMapping[str, Any] = {
            "license": self.LICENSE,
            "as_of": timestamp.isoformat(),
            "requests": requests_meta,
            "start": start_ts.isoformat() if start_ts is not None else None,
        }
        return IngestArtifact(
            source=self.SOURCE,
            path=path,
            data=combined,
            metadata=metadata,
        )

