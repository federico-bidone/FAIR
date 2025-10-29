"""Test end-to-end per ``TRPanelBuilder`` con dati sintetici."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.etl import make_tr_panel
from fair3.engine.utils import io as io_utils


def test_tr_panel_builder_senza_file_raw(tmp_path: Path) -> None:
    """L'assenza di CSV deve fermare l'ETL con un messaggio chiaro."""

    builder = make_tr_panel.TRPanelBuilder(
        raw_root=tmp_path / "raw",
        clean_root=tmp_path / "clean",
        audit_root=tmp_path / "audit",
    )
    builder.raw_root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(FileNotFoundError, match="Nessun file raw trovato"):
        builder.build()


def test_tr_panel_builder_pipeline_minima(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """La pipeline deve produrre artefatti coerenti e log QA in italiano."""

    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    audit_root = tmp_path / "audit"
    (raw_root / "asset").mkdir(parents=True)
    (raw_root / "fx").mkdir(parents=True)

    asset_csv = raw_root / "asset" / "AAA.csv"
    asset_csv.write_text(
        "date,value,symbol,currency\n2023-01-02,10,AAA,USD\n2023-01-03,11,AAA,USD\n",
        encoding="utf-8",
    )
    fx_csv = raw_root / "fx" / "EURUSD.csv"
    fx_csv.write_text(
        "date,value,symbol\n2023-01-02,0.5,EUR/USD\n",
        encoding="utf-8",
    )

    salvati: dict[str, pd.DataFrame] = {}

    def finto_persist(frame: pd.DataFrame, path: Path | str, schema: object) -> tuple[Path, str]:
        io_utils.ensure_dir(Path(path).parent)
        salvati["asset_panel.parquet"] = frame.copy()
        target = Path(path)
        target.write_text("panel\n", encoding="utf-8")
        return target, "checksum"

    monkeypatch.setattr(make_tr_panel, "persist_parquet", finto_persist, raising=False)

    builder = make_tr_panel.TRPanelBuilder(
        raw_root=raw_root,
        clean_root=clean_root,
        audit_root=audit_root,
        base_currency="EUR",
    )
    artefatti = builder.build(seed=1, trace=True)
    stdout = capsys.readouterr().out
    assert "file_raw=2" in stdout

    assert artefatti.panel_path.exists()
    assert artefatti.qa_path.exists()
    assert artefatti.symbols == ["AAA"]
    assert artefatti.rows > 0

    pannello = salvati["asset_panel.parquet"]
    assert {
        "date",
        "symbol",
        "field",
        "value",
        "currency",
        "license",
        "checksum",
    }.issubset(pannello.columns)
    assert (pannello["currency"] == "EUR").all()

    qa_log = pd.read_csv(artefatti.qa_path)
    assert qa_log.iloc[0]["source"] == "asset"
    assert qa_log.iloc[0]["currency"] == "EUR"
