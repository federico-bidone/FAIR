from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.cli.main import main
from fair3.engine.ingest import IngestArtifact

MonkeyPatch = pytest.MonkeyPatch
CaptureFixtureStr = pytest.CaptureFixture[str]


def test_cli_ingest_dispatch(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixtureStr,
) -> None:
    dates = pd.to_datetime(["2024-01-02"])
    data = pd.DataFrame({"date": dates, "value": [1.0], "symbol": ["USD"]})
    artifact_path = tmp_path / "ecb_20240102.csv"
    formatted = data.assign(date=data["date"].dt.strftime("%Y-%m-%d"))
    formatted.to_csv(artifact_path, index=False)
    artifact = IngestArtifact(
        source="ecb",
        path=artifact_path,
        data=data,
        metadata={
            "license": "test",
            "requests": [],
            "as_of": datetime.now(UTC).isoformat(),
        },
    )

    captured: dict[str, object] = {}

    def fake_run_ingest(
        source: str,
        *,
        symbols: list[str] | None = None,
        start: date | None = None,
    ) -> IngestArtifact:
        captured["source"] = source
        captured["symbols"] = symbols
        captured["start"] = start
        return artifact

    monkeypatch.setattr("fair3.cli.main.run_ingest", fake_run_ingest)

    main(["ingest", "--source", "ecb", "--symbols", "USD", "--from", "2024-01-02"])
    out = capsys.readouterr().out
    assert "source=ecb" in out
    assert "rows=1" in out
    assert captured["symbols"] == ["USD"]
    assert str(captured["start"]) == "2024-01-02"
