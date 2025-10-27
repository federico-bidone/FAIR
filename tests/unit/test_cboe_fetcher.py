from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.cboe import CBOEFetcher

MonkeyPatch = pytest.MonkeyPatch


def test_cboe_default_symbols() -> None:
    """The fetcher must expose the documented default tuple."""

    assert CBOEFetcher.DEFAULT_SYMBOLS == ("VIX", "SKEW")


def test_cboe_build_url_validates_symbols() -> None:
    """Unsupported symbols should raise a descriptive error."""

    fetcher = CBOEFetcher()
    url = fetcher.build_url("vix", None)
    assert url == "https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"
    with pytest.raises(ValueError, match="Unsupported CBOE symbol"):
        fetcher.build_url("unknown", None)


def test_cboe_fetch_parses_payloads(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """The fetcher normalises CSV payloads and applies the start filter."""

    fetcher = CBOEFetcher(raw_root=tmp_path)
    payloads = {
        "VIX": "DATE,VIX Close\n2024-01-02,12.5\n2024-01-03,13.2\n",
        "SKEW": "Date,SKEW\n2024-01-02,130.0\n2024-01-04,131.0\n",
    }

    def fake_download(url: str, session: object | None = None) -> str:
        if url.endswith("VIX_History.csv"):
            return payloads["VIX"]
        if url.endswith("SKEW_History.csv"):
            return payloads["SKEW"]
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(fetcher, "_download", fake_download)
    artifact = fetcher.fetch(
        symbols=["VIX", "SKEW"],
        start=pd.Timestamp("2024-01-03"),
        as_of=datetime.now(UTC),
    )
    frame = artifact.data
    assert list(frame["symbol"].unique()) == ["VIX", "SKEW"]
    vix_rows = frame[frame["symbol"] == "VIX"]
    assert vix_rows.shape[0] == 1
    assert vix_rows.iloc[0]["date"] == pd.Timestamp("2024-01-03")
    assert pytest.approx(vix_rows.iloc[0]["value"], rel=1e-9) == 13.2
    skew_rows = frame[frame["symbol"] == "SKEW"]
    assert pytest.approx(skew_rows.iloc[0]["value"], rel=1e-9) == 131.0
    assert artifact.metadata["license"] == CBOEFetcher.LICENSE


def test_cboe_parse_rejects_html() -> None:
    """HTML payloads should be rejected with a clear error."""

    fetcher = CBOEFetcher()
    with pytest.raises(ValueError, match="HTML"):
        fetcher.parse("<html>Error</html>", "VIX")
