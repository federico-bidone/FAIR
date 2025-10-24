from __future__ import annotations

from pathlib import Path

import pytest

from fair3.cli.main import main


def test_cli_goals_runs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / "goals"
    main(
        [
            "goals",
            "--draws",
            "256",
            "--seed",
            "12",
            "--output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()
    assert "[fair3] goals draws=256" in captured.out
    summary_path = output_dir / "goals" / "summary.csv"
    assert summary_path.exists()
