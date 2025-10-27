"""Unit test per il fetcher LBMA."""

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.lbma import LBMAFetcher

HTML_PAYLOAD = """
<html>
  <body>
    <table>
      <thead>
        <tr><th>Date</th><th>USD (PM)</th></tr>
      </thead>
      <tbody>
        <tr><td>02 Jan 2024</td><td>2050.10</td></tr>
        <tr><td>03 Jan 2024</td><td>2040.00</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""


def test_lbma_default_symbols() -> None:
    """Verifica che i simboli di default coprano oro e argento."""

    assert LBMAFetcher.DEFAULT_SYMBOLS == ("gold_pm", "silver_pm")


def test_lbma_fetch_parses_payload(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Il fetcher converte i fixing in EUR e popola pit_flag."""

    fetcher = LBMAFetcher(
        raw_root=tmp_path,
        fx_rates={"2024-01-02": 0.92, "2024-01-03": 0.91},
    )

    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: HTML_PAYLOAD)

    artifact = fetcher.fetch(symbols=["gold_pm"], start=None)

    assert artifact.source == "lbma"
    assert artifact.metadata["license"] == fetcher.LICENSE
    assert not artifact.data.empty
    first_row = artifact.data.iloc[0]
    assert first_row["currency"] == "EUR"
    assert first_row["pit_flag"] == 1
    # Prezzo USD (2050.10) * cambio 0.92 → 1886.092 ~
    assert pytest.approx(first_row["value"], rel=1e-6) == 2050.10 * 0.92
    # Timestamp atteso 2024-01-02 15:00 UTC → 2024-01-02 15:00 (naive)
    assert first_row["date"] == pd.Timestamp("2024-01-02 15:00:00")


def test_lbma_parse_rejects_empty_html() -> None:
    """Il parser rifiuta payload HTML privi di tabella dati."""

    fetcher = LBMAFetcher()
    html = "<html><body><h1>Access denied</h1></body></html>"
    with pytest.raises(ValueError, match="HTML without data"):
        fetcher.parse(html, "gold_pm")


def test_lbma_parse_requires_fx(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'assenza di cambi disponibili genera un errore chiaro."""

    fetcher = LBMAFetcher()

    def fail(_: object) -> None:
        raise ValueError("FX missing")

    monkeypatch.setattr(fetcher, "_load_fx_rates", fail)
    with pytest.raises(ValueError, match="FX missing"):
        fetcher.parse(HTML_PAYLOAD, "gold_pm")


def test_lbma_build_url_validates_symbol() -> None:
    """Il fetcher valida i simboli sconosciuti."""

    fetcher = LBMAFetcher()
    with pytest.raises(ValueError, match="Unsupported LBMA symbol"):
        fetcher.build_url("platinum_am", None)
