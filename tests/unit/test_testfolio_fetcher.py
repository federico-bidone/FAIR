"""Unit test per il fetcher testfol.io basato su configurazioni manuali.

Il modulo verifica che la composizione dei segmenti dichiarativi produca serie
deterministiche, che gli aggiustamenti annualizzati vengano applicati
correttamente e che i metadati audit riflettano i file YAML utilizzati.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from fair3.engine.ingest.testfolio import TestfolioPresetFetcher, curate_testfolio_presets


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    """Salva un DataFrame in CSV con encoding UTF-8 senza indice.

    Args:
        path: Percorso di destinazione.
        frame: Dati da serializzare.

    Returns:
        None.

    Raises:
        OSError: Se il file non può essere scritto.
    """

    path.write_text(frame.to_csv(index=False), encoding="utf-8")


def test_curate_testfolio_presets_combines_segments(tmp_path: Path) -> None:
    """La funzione di curazione deve concatenare segmenti e applicare bonus annuo."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    config_path = tmp_path / "config.yml"

    pre_segment = pd.DataFrame(
        {
            "Date": ["2000-01-01", "2000-02-01"],
            "Return": [1.0, 1.5],
        }
    )
    modern_segment = pd.DataFrame(
        {
            "date": ["2000-03-31", "2000-04-30"],
            "total_return": [0.03, 0.04],
        }
    )
    _write_csv(manual_dir / "spysim_pre.csv", pre_segment)
    _write_csv(manual_dir / "spysim_modern.csv", modern_segment)

    config_payload = {
        "presets": {
            "SPYSIM": {
                "frequency": "monthly",
                "segments": [
                    {
                        "loader": "manual_csv",
                        "path": "spysim_pre.csv",
                        "date_column": "Date",
                        "value_column": "Return",
                        "scale": 0.01,
                        "month_end_align": True,
                    },
                    {
                        "loader": "manual_csv",
                        "path": "spysim_modern.csv",
                        "date_column": "date",
                        "value_column": "total_return",
                        "annualized_adjustment": 0.12,
                    },
                ],
            }
        }
    }
    config_path.write_text(yaml.safe_dump(config_payload), encoding="utf-8")

    presets = curate_testfolio_presets(config_path, manual_root=manual_dir)
    assert set(presets.keys()) == {"SPYSIM"}
    frame = presets["SPYSIM"]
    assert len(frame) == 4
    assert frame["symbol"].unique().tolist() == ["SPYSIM"]
    # La prima riga deve essere allineata a fine mese e scalata a decimale.
    assert frame.loc[0, "date"].day == 31
    assert pytest.approx(frame.loc[0, "value"], rel=1e-9) == 0.01
    # Il segmento moderno deve applicare il bonus annualizzato convertito in mensile.
    monthly_bonus = (1.0 + 0.12) ** (1.0 / 12.0) - 1.0
    assert pytest.approx(frame.loc[3, "value"], rel=1e-9) == 0.04 + monthly_bonus


def test_testfolio_fetcher_filters_start_and_emits_metadata(tmp_path: Path) -> None:
    """Il fetcher deve filtrare per start-date e riportare il percorso YAML nei metadati."""

    manual_dir = tmp_path / "manual"
    raw_root = tmp_path / "raw"
    manual_dir.mkdir()
    raw_root.mkdir()

    pre_segment = pd.DataFrame(
        {
            "Date": ["2019-01-01", "2019-02-01"],
            "Return": [1.0, 2.0],
        }
    )
    modern_segment = pd.DataFrame(
        {
            "date": ["2019-03-31", "2019-04-30"],
            "total_return": [0.03, 0.04],
        }
    )
    _write_csv(manual_dir / "preset_pre.csv", pre_segment)
    _write_csv(manual_dir / "preset_modern.csv", modern_segment)

    config_payload = {
        "presets": {
            "VTISIM": {
                "frequency": "monthly",
                "segments": [
                    {
                        "path": "preset_pre.csv",
                        "date_column": "Date",
                        "value_column": "Return",
                        "scale": 0.01,
                        "month_end_align": True,
                    },
                    {
                        "path": "preset_modern.csv",
                        "date_column": "date",
                        "value_column": "total_return",
                    },
                ],
            }
        }
    }
    config_path = tmp_path / "config.yml"
    config_path.write_text(yaml.safe_dump(config_payload), encoding="utf-8")

    fetcher = TestfolioPresetFetcher(
        config_path=config_path,
        manual_root=manual_dir,
        raw_root=raw_root,
    )
    artifact = fetcher.fetch(symbols=["VTISIM"], start=date(2019, 3, 1))

    assert artifact.data["symbol"].unique().tolist() == ["VTISIM"]
    assert artifact.data["date"].min() >= pd.Timestamp("2019-03-01")
    assert artifact.metadata["license"].startswith("testfol.io synthetic")
    assert artifact.metadata["requests"][0]["config"] == str(config_path)
    assert artifact.metadata["requests"][0]["rows"] == len(artifact.data)
    assert artifact.path.exists()


def test_curate_testfolio_presets_missing_file(tmp_path: Path) -> None:
    """Quando un segmento manca il fetcher deve segnalare FileNotFoundError."""

    manual_dir = tmp_path / "manual"
    manual_dir.mkdir()
    config_path = tmp_path / "config.yml"
    config_payload = {
        "presets": {
            "GLDSIM": {
                "frequency": "monthly",
                "segments": [
                    {
                        "path": "missing.csv",
                    }
                ],
            }
        }
    }
    config_path.write_text(yaml.safe_dump(config_payload), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        curate_testfolio_presets(config_path, manual_root=manual_dir)
