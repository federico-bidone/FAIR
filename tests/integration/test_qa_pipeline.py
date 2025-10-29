"""Integration tests for the deterministic QA pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from fair3.engine.qa import DemoQAConfig, run_demo_qa


def test_run_demo_qa_creates_artifacts(tmp_path: Path) -> None:
    """The QA pipeline should produce reports and robustness artefacts.

    Args:
        tmp_path: Temporary directory supplied by pytest.
    """

    config = DemoQAConfig(
        label="test",  # use distinct label to avoid collisions
        start=pd.Timestamp("2020-01-01"),
        end=pd.Timestamp("2021-12-31"),
        output_dir=tmp_path,
        robustness_draws=32,
        robustness_block_size=12,
        cv_splits=2,
    )
    result = run_demo_qa(config)

    assert result.report_pdf.exists() and result.report_pdf.stat().st_size > 0
    assert result.robustness_report.exists() and result.robustness_report.stat().st_size > 0
    assert result.ablation_csv.exists()

    acceptance_payload = json.loads(result.acceptance_json.read_text(encoding="utf-8"))
    assert "passes" in acceptance_payload

    robustness_payload = json.loads(result.robustness_summary.read_text(encoding="utf-8"))
    assert "passes" in robustness_payload

    # The QA helper should expose boolean flags for downstream CI assertions.
    assert isinstance(result.acceptance_passed, bool)
    assert isinstance(result.robustness_passed, bool)
