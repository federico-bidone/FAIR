from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from fair3.engine.ingest.portfolio_visualizer import PortfolioVisualizerFetcher


def _write_csv(path: Path, content: str) -> None:
    """Scrive testo CSV di supporto con encoding UTF-8."""

    path.write_text(content, encoding="utf-8")


def test_portviz_parsing_filters_start(tmp_path: Path) -> None:
    """Il fetcher deve scalare le percentuali e filtrare la data minima."""

    manual_dir = tmp_path
    csv_path = manual_dir / "US_Total_Stock_Market.csv"
    _write_csv(
        csv_path,
        "Date,Return\n2023-12-31,1.5\n2024-01-31,2.0\n",
    )
    fetcher = PortfolioVisualizerFetcher(manual_root=manual_dir, raw_root=tmp_path)
    artifact = fetcher.fetch(symbols=["us_total_stock_market"], start=date(2024, 1, 1))

    assert artifact.metadata["license"] == fetcher.LICENSE
    assert artifact.data.iloc[0]["symbol"] == "us_total_stock_market"
    assert artifact.data.iloc[0]["date"].date() == date(2024, 1, 31)
    assert pytest.approx(float(artifact.data.iloc[0]["value"]), rel=1e-9) == 0.02


def test_portviz_missing_file(tmp_path: Path) -> None:
    """Se il file manuale non è presente deve essere sollevato FileNotFoundError."""

    fetcher = PortfolioVisualizerFetcher(manual_root=tmp_path, raw_root=tmp_path)
    with pytest.raises(FileNotFoundError):
        fetcher.fetch(symbols=["us_total_stock_market"])


def test_portviz_missing_columns(tmp_path: Path) -> None:
    """Il parser deve segnalare colonne mancanti nel CSV manuale."""

    manual_dir = tmp_path
    csv_path = manual_dir / "US_Total_Stock_Market.csv"
    _write_csv(csv_path, "Data,Valore\n2024-01-31,1.0\n")
    fetcher = PortfolioVisualizerFetcher(manual_root=manual_dir, raw_root=tmp_path)

    with pytest.raises(ValueError, match="Missing expected columns"):
        fetcher.fetch(symbols=["us_total_stock_market"])


def test_portviz_html_guard(tmp_path: Path) -> None:
    """Il parser deve rifiutare payload HTML accidentali."""

    manual_dir = tmp_path
    csv_path = manual_dir / "US_Total_Stock_Market.csv"
    _write_csv(csv_path, "<html>blocked</html>")
    fetcher = PortfolioVisualizerFetcher(manual_root=manual_dir, raw_root=tmp_path)

    with pytest.raises(ValueError, match="Unexpected HTML payload"):
        fetcher.fetch(symbols=["us_total_stock_market"])
