from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest import (
    BOEFetcher,
    ECBFetcher,
    FREDFetcher,
    StooqFetcher,
    available_sources,
    create_fetcher,
)

MonkeyPatch = pytest.MonkeyPatch


class RecordingLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(  # pragma: no cover - simple recorder
        self,
        message: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        if args:
            self.messages.append(message % args)
        else:
            self.messages.append(message)


TIMESTAMP = datetime(2024, 1, 31, 15, 0, tzinfo=UTC)


@pytest.mark.parametrize("source", ["aqr", "boe", "ecb", "fred", "french", "stooq"])
def test_available_sources_contains_defaults(source: str) -> None:
    assert source in available_sources()


def test_create_fetcher_returns_instance(tmp_path: Path) -> None:
    fetcher = create_fetcher("ecb", raw_root=tmp_path)
    assert isinstance(fetcher, ECBFetcher)


def _write_and_validate(result_path: Path, expected_rows: int) -> pd.DataFrame:
    assert result_path.exists()
    frame = pd.read_csv(result_path)
    for column in ("date", "value", "symbol"):
        assert column in frame.columns
    assert len(frame) == expected_rows
    return frame


def test_ecb_fetcher(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    logger = RecordingLogger()
    fetcher = ECBFetcher(raw_root=tmp_path, logger=logger)
    sample = "TIME_PERIOD,OBS_VALUE\n2024-01-01,1.1\n2024-01-02,1.2\n"
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: sample)
    result = fetcher.fetch(symbols=["USD"], start=date(2024, 1, 2), as_of=TIMESTAMP)
    assert result.metadata["license"] == ECBFetcher.LICENSE
    assert result.metadata["requests"][0]["symbol"] == "USD"
    frame = _write_and_validate(result.path, 1)
    assert frame.loc[0, "date"] == "2024-01-02"
    assert any("license" in msg for msg in logger.messages)


def test_fred_fetcher_filters_start(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    logger = RecordingLogger()
    monkeypatch.setenv("FRED_API_KEY", "D" * 32)
    fetcher = FREDFetcher(raw_root=tmp_path, logger=logger)
    sample = """{"observations": [
        {"date": "2023-12-31", "value": "0.5"},
        {"date": "2024-01-05", "value": "1.0"}
    ]}"""
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: sample)
    result = fetcher.fetch(symbols=["DGS10"], start=date(2024, 1, 1), as_of=TIMESTAMP)
    assert len(result.data) == 1
    frame = _write_and_validate(result.path, 1)
    assert frame.loc[0, "value"] == pytest.approx(1.0)
    assert result.metadata["requests"][0]["url"].startswith(FREDFetcher.BASE_URL)


def test_boe_fetcher(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    logger = RecordingLogger()
    fetcher = BOEFetcher(raw_root=tmp_path, logger=logger)
    sample = "01/01/2024,3.5\n"
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: sample)
    result = fetcher.fetch(symbols=["IUMGBP"], as_of=TIMESTAMP)
    frame = _write_and_validate(result.path, 1)
    assert frame.loc[0, "symbol"] == "IUMGBP"
    assert result.metadata["requests"][0]["symbol"] == "IUMGBP"


def test_stooq_fetcher(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    logger = RecordingLogger()
    fetcher = StooqFetcher(raw_root=tmp_path, logger=logger)
    sample = "Date,Open,High,Low,Close,Volume\n2024-01-02,1,1,1,2.5,100\n"
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: sample)
    result = fetcher.fetch(symbols=["spx"], as_of=TIMESTAMP)
    frame = _write_and_validate(result.path, 1)
    assert frame.loc[0, "value"] == pytest.approx(2.5)
    assert frame.loc[0, "tz"] == "Europe/Warsaw"
    assert any("ingest_complete" in msg for msg in logger.messages)
