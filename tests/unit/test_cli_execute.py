from __future__ import annotations

import pytest

from fair3.cli.main import main as cli_main


def test_cli_execute_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["execute", "--rebalance-date", "2025-10-20", "--dry-run"]
    cli_main(argv)
    captured = capsys.readouterr().out
    assert "[fair3] execute dry-run" in captured
    assert "decision=hold" in captured
