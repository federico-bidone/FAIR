from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.cli.main import main as cli_main


def _create_raw(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    audit_root = tmp_path / "audit"
    dates = pd.date_range("2022-01-03", periods=5, freq="B")
    frame = pd.DataFrame({"date": dates, "value": [1, 1.1, 1.2, 1.3, 1.4], "symbol": "CLI"})
    path = raw_root / "ecb" / "cli.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return raw_root, clean_root, audit_root


def test_cli_etl_rebuild(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    raw_root, clean_root, audit_root = _create_raw(tmp_path)
    argv = [
        "etl",
        "--rebuild",
        "--raw-root",
        str(raw_root),
        "--clean-root",
        str(clean_root),
        "--audit-root",
        str(audit_root),
    ]
    cli_main(argv)
    captured = capsys.readouterr().out
    assert "[fair3] etl" in captured
    assert (clean_root / "prices.parquet").exists()
    assert (clean_root / "returns.parquet").exists()
    assert (clean_root / "features.parquet").exists()
    assert (audit_root / "qa_data_log.csv").exists()
