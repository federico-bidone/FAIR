"""Unit test per il fetcher PortfolioCharts Simba."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest import portfoliocharts


class _DummyExcelFile:
    """Semplice stub per simulare ``pandas.ExcelFile`` nei test unitari."""

    def __init__(self, data_map: dict[str, pd.DataFrame]) -> None:
        self._data_map = data_map

    def __enter__(self) -> _DummyExcelFile:  # pragma: no cover - trivial
        return self

    def __exit__(self, *_: object) -> bool:  # pragma: no cover - trivial
        return False

    def parse(self, sheet_name: str) -> pd.DataFrame:
        """Restituisce il DataFrame fittizio associato al foglio richiesto."""

        return self._data_map[sheet_name]


def test_parse_portfoliocharts_simba_normalizes_month_end(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifica il parsing del workbook Simba con mapping di default."""

    data_series = pd.DataFrame(
        {
            "Date": ["2020-01-01", "2020-02-01"],
            "US Large Cap": [10.0, 11.0],
            "US Mid Cap": [20.0, 21.0],
            "US Small Cap": [30.0, 31.0],
            "International Stocks": [40.0, None],
            "Emerging Markets": [50.0, 51.0],
            "US Bonds": [60.0, 61.0],
            "International Bonds": [70.0, 71.0],
        }
    )
    stocks = pd.DataFrame(
        {
            "Date": ["2020-01-01", "2020-02-01"],
            "Large Cap Value": [1.0, 1.1],
            "Large Cap Growth": [1.2, 1.3],
            "Small Cap Value": [1.4, 1.5],
            "Small Cap Growth": [1.6, 1.7],
        }
    )
    workbook_data = {
        "Data_Series": data_series,
        "Stocks": stocks,
    }

    def _factory(_: Path) -> _DummyExcelFile:
        return _DummyExcelFile(workbook_data)

    monkeypatch.setattr(portfoliocharts.pd, "ExcelFile", _factory)
    workbook_path = tmp_path / "PortfolioCharts_Simba.xlsx"
    workbook_path.write_bytes(b"dummy")

    frame, metadata = portfoliocharts.parse_portfoliocharts_simba(workbook_path)

    assert "US_LARGE_CAP" in metadata
    assert metadata["US_LARGE_CAP"] == {"sheet": "Data_Series", "column": "US Large Cap"}
    assert metadata["US_LARGE_VALUE"] == {"sheet": "Stocks", "column": "Large Cap Value"}

    large_cap = frame[frame["symbol"] == "US_LARGE_CAP"].reset_index(drop=True)
    assert list(large_cap["date"]) == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-29")]
    assert list(large_cap["value"]) == [10.0, 11.0]

    intl_stocks = frame[frame["symbol"] == "INTL_DEVELOPED_EQ"].reset_index(drop=True)
    # La riga con ``None`` viene rimossa dal parser.
    assert len(intl_stocks) == 1
    assert intl_stocks.iloc[0]["date"] == pd.Timestamp("2020-01-31")


def test_portfoliocharts_fetcher_filters_and_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verifica che il fetcher filtri per simbolo e propaghi i metadati."""

    workbook_path = tmp_path / portfoliocharts.DEFAULT_WORKBOOK_NAME
    workbook_path.write_text("placeholder")

    sample_data = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-31", "2020-02-29", "2020-01-31", "2020-02-29"]),
            "symbol": [
                "US_LARGE_CAP",
                "US_LARGE_CAP",
                "US_MID_CAP",
                "US_MID_CAP",
            ],
            "value": [100.0, 101.0, 200.0, 201.0],
        }
    )
    metadata_map = {
        "US_LARGE_CAP": {"sheet": "Data_Series", "column": "US Large Cap"},
        "US_MID_CAP": {"sheet": "Data_Series", "column": "US Mid Cap"},
    }

    def _parse_stub(
        path: Path, *, mapping: object | None = None
    ) -> tuple[pd.DataFrame, dict[str, dict[str, str]]]:  # noqa: D401
        del path, mapping
        return sample_data, metadata_map

    monkeypatch.setattr(portfoliocharts, "parse_portfoliocharts_simba", _parse_stub)
    raw_root = tmp_path / "raw"
    fetcher = portfoliocharts.PortfolioChartsFetcher(
        manual_root=tmp_path,
        raw_root=raw_root,
    )

    artifact = fetcher.fetch(symbols=["US_LARGE_CAP"], start="2020-02-01")

    assert artifact.data["symbol"].unique().tolist() == ["US_LARGE_CAP"]
    assert artifact.data["date"].tolist() == [pd.Timestamp("2020-02-29")]
    assert artifact.metadata["license"] == portfoliocharts.PortfolioChartsFetcher.LICENSE
    assert artifact.metadata["requests"][0]["column"] == "US Large Cap"
    assert artifact.path.exists()
    assert artifact.path.parent == raw_root / "portfoliocharts"


def test_portfoliocharts_fetcher_missing_file(tmp_path: Path) -> None:
    """Il fetcher solleva ``FileNotFoundError`` se il workbook manca."""

    fetcher = portfoliocharts.PortfolioChartsFetcher(manual_root=tmp_path)
    with pytest.raises(FileNotFoundError):
        fetcher.fetch(symbols=["US_LARGE_CAP"])
