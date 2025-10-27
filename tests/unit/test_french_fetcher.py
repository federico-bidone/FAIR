"""Tests for the Kenneth R. French ingest fetcher."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest

from fair3.engine.ingest.french import FrenchFetcher

MonkeyPatch = pytest.MonkeyPatch


def _zip_payload(text: str, *, inner: str = "sample.txt") -> bytes:
    """Create an in-memory ZIP archive that mimics the French FTP payload."""

    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(inner, text)
    return buffer.getvalue()


def test_french_default_symbols() -> None:
    """The fetcher must expose the documented default dataset tuple."""

    assert FrenchFetcher.DEFAULT_SYMBOLS == (
        "research_factors_monthly",
        "five_factors_2x3",
        "momentum",
        "industry_49",
    )


def test_french_fetch_parses_monthly_payload(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Monthly factor payloads are parsed, scaled, and reshaped correctly."""

    fetcher = FrenchFetcher(raw_root=tmp_path)
    payload = _zip_payload(
        """
        Header information
        Mkt-RF SMB HML RF
        192607 1.23 0.45 -0.12 0.03
        192608 0.50 -0.25 0.10 0.02

        Annual Factors:
        """
    )
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: payload)
    artifact = fetcher.fetch(symbols=["research_factors_monthly"], as_of=datetime.now(UTC))
    frame = artifact.data
    assert set(frame["symbol"].unique()) == {
        "research_factors_monthly_mkt_rf",
        "research_factors_monthly_smb",
        "research_factors_monthly_hml",
        "research_factors_monthly_rf",
    }
    assert frame["date"].min() == pd.Timestamp("1926-07-01")
    sample = frame.loc[frame["symbol"] == "research_factors_monthly_mkt_rf", "value"].iloc[0]
    assert pytest.approx(sample, rel=1e-9) == 0.0123
    assert artifact.metadata["license"] == FrenchFetcher.LICENSE


def test_french_fetch_infers_header_when_missing(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Datasets without explicit column lists still yield sensible identifiers."""

    fetcher = FrenchFetcher(raw_root=tmp_path)
    payload = _zip_payload(
        """
        Industries
        Agric Food Soda
        192607 1.0 2.0 3.0
        192608 1.5 2.5 3.5

        Summary section
        """
    )
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: payload)
    artifact = fetcher.fetch(symbols=["industry_49"], as_of=datetime.now(UTC))
    frame = artifact.data
    assert set(frame["symbol"].unique()) == {
        "industry_49_agric",
        "industry_49_food",
        "industry_49_soda",
    }
    assert len(frame) == 6
    assert pytest.approx(frame["value"].iloc[0], rel=1e-9) == 0.01
