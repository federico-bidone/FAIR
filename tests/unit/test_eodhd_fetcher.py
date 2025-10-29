"""Unit test per il fetcher EOD Historical Data/backtes.to."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.eodhd import EODHDFetcher


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    """Persistenza helper per CSV UTF-8 senza indice.

    Args:
        path: Percorso destinazione.
        frame: Dati da serializzare.

    Returns:
        None.

    Raises:
        OSError: Se la scrittura fallisce.
    """

    path.write_text(frame.to_csv(index=False), encoding="utf-8")


def test_eodhd_fetcher_manual_roundtrip(tmp_path: Path) -> None:
    """Il fetcher deve leggere CSV manuali e rispettare il filtro ``start``.

    Args:
        tmp_path: Directory temporanea popolata da pytest.

    Returns:
        None.

    Raises:
        AssertionError: Se la serie risultante non corrisponde alle attese.
    """

    manual_dir = tmp_path / "eodhd"
    raw_root = tmp_path / "raw"
    manual_dir.mkdir()
    raw_root.mkdir()
    frame = pd.DataFrame(
        {
            "Date": ["2020-01-31", "2020-02-29"],
            "Adjusted Close": [320.5, 325.1],
        }
    )
    _write_csv(manual_dir / "SPY.US.csv", frame)

    fetcher = EODHDFetcher(manual_root=manual_dir, raw_root=raw_root)
    artifact = fetcher.fetch(symbols=["SPY.US"], start=date(2020, 2, 1))

    assert artifact.metadata["license"] == EODHDFetcher.LICENSE
    assert artifact.metadata["requests"] == [
        {"symbol": "SPY.US", "url": f"manual://{manual_dir / 'SPY.US.csv'}"}
    ]
    assert len(artifact.data) == 1
    row = artifact.data.iloc[0]
    assert row["symbol"] == "SPY.US"
    assert row["date"] == pd.Timestamp("2020-02-29")
    assert pytest.approx(row["value"], rel=1e-9) == 325.1


def test_eodhd_fetcher_api_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Quando manca il CSV manuale l'API JSON deve essere interpretata correttamente.

    Args:
        monkeypatch: Fixture pytest per sostituire la logica di download.
        tmp_path: Directory temporanea popolata da pytest.

    Returns:
        None.

    Raises:
        AssertionError: Se il parsing del payload JSON non restituisce i valori attesi.
    """

    manual_dir = tmp_path / "eodhd"
    raw_root = tmp_path / "raw"
    manual_dir.mkdir()
    raw_root.mkdir()
    fetcher = EODHDFetcher(manual_root=manual_dir, raw_root=raw_root, api_token="TOKEN123")

    captured_urls: list[str] = []

    def fake_download(url: str, session: object | None = None) -> str:
        captured_urls.append(url)
        payload = [
            {"date": "2020-01-31", "adjusted_close": 300.0},
            {"date": "2020-02-29", "close": 305.5},
        ]
        return json.dumps(payload)

    monkeypatch.setattr(fetcher, "_download", fake_download)
    artifact = fetcher.fetch(symbols=["SPY.US"], start=date(2020, 1, 1))

    assert captured_urls, "_download deve essere stato invocato"
    url = captured_urls[0]
    assert "api_token=TOKEN123" in url
    assert "period=m" in url
    assert "from=2020-01-01" in url
    values = artifact.data.sort_values("date")
    assert values.iloc[0]["value"] == pytest.approx(300.0, rel=1e-9)
    assert values.iloc[1]["value"] == pytest.approx(305.5, rel=1e-9)


def test_eodhd_fetcher_requires_manual_or_token(tmp_path: Path) -> None:
    """L'assenza di file manuali e token deve produrre ``FileNotFoundError``.

    Args:
        tmp_path: Directory temporanea popolata da pytest.

    Returns:
        None.

    Raises:
        AssertionError: Se il fetcher non solleva l'eccezione attesa.
    """

    manual_dir = tmp_path / "eodhd"
    manual_dir.mkdir()
    fetcher = EODHDFetcher(manual_root=manual_dir)

    with pytest.raises(FileNotFoundError, match="manual file not found"):
        fetcher.fetch(symbols=["SPY.US"])


def test_eodhd_fetcher_detects_html(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Il parser deve rigettare payload HTML provenienti dall'endpoint API.

    Args:
        monkeypatch: Fixture pytest per simulare una risposta HTML.
        tmp_path: Directory temporanea popolata da pytest.

    Returns:
        None.

    Raises:
        AssertionError: Se il fetcher non intercetta il payload HTML come errore.
    """

    manual_dir = tmp_path / "eodhd"
    raw_root = tmp_path / "raw"
    manual_dir.mkdir()
    raw_root.mkdir()
    fetcher = EODHDFetcher(manual_root=manual_dir, raw_root=raw_root, api_token="TOKEN123")

    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: "<html>Error</html>")

    with pytest.raises(ValueError, match="HTML payload"):
        fetcher.fetch(symbols=["SPY.US"])
