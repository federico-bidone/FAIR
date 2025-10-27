"""Unit tests for the OECD SDMX ingest fetcher."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from fair3.engine.ingest.oecd import OECDFetcher

MonkeyPatch = pytest.MonkeyPatch


def test_oecd_default_symbols() -> None:
    """The fetcher exposes the documented CLI defaults."""

    assert OECDFetcher.DEFAULT_SYMBOLS == (
        "MEI_CLI/LOLITOAA.IT.A",
        "MEI_CLI/LOLITOAA.EA19.A",
    )


def test_oecd_build_url_merges_params() -> None:
    """StartTime and default query parameters must be encoded in the URL."""

    fetcher = OECDFetcher()
    start = pd.Timestamp("2015-06-17")
    url = fetcher.build_url("MEI_CLI/LOLITOAA.IT.A", start)
    parsed = urlparse(url)
    assert parsed.path.endswith("/MEI_CLI/LOLITOAA.IT.A")
    query = parse_qs(parsed.query)
    assert query["contentType"] == ["csv"]
    assert query["dimensionAtObservation"] == ["TimeDimension"]
    assert query["timeOrder"] == ["Ascending"]
    assert query["startTime"] == ["2015-06-17"]


def test_oecd_build_url_accepts_extra_query() -> None:
    """Symbol query strings must override defaults when provided."""

    fetcher = OECDFetcher()
    url = fetcher.build_url("MEI_CLI/LOLITOAA.IT.A?detail=series", None)
    query = parse_qs(urlparse(url).query)
    assert query["detail"] == ["series"]


def test_oecd_parse_normalises_payload(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """CSV payloads are converted to the FAIR ingest schema."""

    fetcher = OECDFetcher(raw_root=tmp_path)
    payload = (
        "LOCATION,SUBJECT,MEASURE,FREQUENCY,TIME_PERIOD,OBS_VALUE\n"
        "ITA,LOLITOAA,AMSM,Monthly,2020-01,100.1\n"
        "ITA,LOLITOAA,AMSM,Monthly,2020-02,100.4\n"
    )
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: payload)
    artifact = fetcher.fetch(symbols=["MEI_CLI/LOLITOAA.IT.A"], as_of=datetime.now(UTC))
    frame = artifact.data
    assert frame["symbol"].tolist() == ["MEI_CLI/LOLITOAA.IT.A", "MEI_CLI/LOLITOAA.IT.A"]
    assert frame["date"].tolist() == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-01")]
    assert pytest.approx(frame["value"].tolist(), rel=1e-9) == [100.1, 100.4]
    assert artifact.metadata["license"] == OECDFetcher.LICENSE


def test_oecd_parse_rejects_html() -> None:
    """HTML payloads must be rejected to highlight rate-limit pages."""

    fetcher = OECDFetcher()
    with pytest.raises(ValueError, match="payload HTML"):
        fetcher.parse("<html>blocked</html>", "MEI_CLI/LOLITOAA.IT.A")


def test_oecd_parse_requires_value_column() -> None:
    """Missing OBS_VALUE/VALUE columns should raise a descriptive error."""

    fetcher = OECDFetcher()
    csv = "TIME_PERIOD\n2020-01\n"
    with pytest.raises(ValueError, match="missing OBS_VALUE"):
        fetcher.parse(csv, "MEI_CLI/LOLITOAA.IT.A")
