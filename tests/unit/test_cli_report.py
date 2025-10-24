from __future__ import annotations

from pathlib import Path

import pytest

from fair3.cli.main import main
from fair3.engine.utils.io import safe_path_segment


def test_cli_report_monthly(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output_dir = tmp_path / "reports"
    main(
        [
            "report",
            "--period",
            "2024-01:2024-03",
            "--monthly",
            "--seed",
            "5",
            "--output-dir",
            str(output_dir),
        ]
    )
    captured = capsys.readouterr()
    assert "report monthly period=2024-01:2024-03" in captured.out
    expected_dir = Path(output_dir) / safe_path_segment("2024-01:2024-03")
    assert expected_dir.exists()
