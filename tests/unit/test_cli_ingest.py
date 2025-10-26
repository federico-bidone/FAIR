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
    monkeypatch.chdir(tmp_path)
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
        progress: bool = False,
    ) -> IngestArtifact:
        captured["source"] = source
        captured["symbols"] = symbols
        captured["start"] = start
        captured["progress"] = progress
        return artifact

    monkeypatch.setattr("fair3.cli.main.run_ingest", fake_run_ingest)

    main(["ingest", "--source", "ecb", "--symbols", "USD", "--from", "2024-01-02"])
    out = capsys.readouterr().out
    assert "source=ecb" in out
    assert "rows=1" in out
    assert captured["symbols"] == ["USD"]
    assert str(captured["start"]) == "2024-01-02"
    assert captured["progress"] is False


def test_cli_ingest_respects_global_flags(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: CaptureFixtureStr,
) -> None:
    monkeypatch.chdir(tmp_path)
    artifact = IngestArtifact(
        source="ecb",
        path=tmp_path / "ecb.csv",
        data=pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "value": [1.0],
                "symbol": ["USD"],
            }
        ),
        metadata={},
    )

    called: dict[str, object] = {}

    def fake_configure(json_logs: bool) -> None:
        called["json_logs"] = json_logs

    def fake_run_ingest(
        source: str,
        *,
        symbols: list[str] | None = None,
        start: date | None = None,
        progress: bool = False,
    ) -> IngestArtifact:
        called["progress"] = progress
        return artifact

    monkeypatch.setattr("fair3.cli.main.configure_cli_logging", fake_configure)
    monkeypatch.setattr("fair3.cli.main.run_ingest", fake_run_ingest)

    main(
        [
            "--json-logs",
            "--progress",
            "ingest",
            "--source",
            "ecb",
            "--symbols",
            "USD",
            "--from",
            "2024-01-02",
        ]
    )
    capsys.readouterr()
    assert called["json_logs"] is True
    assert called["progress"] is True
