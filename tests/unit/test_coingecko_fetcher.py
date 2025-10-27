"""Test per CoinGeckoFetcher."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import pandas as pd
import pytest

from fair3.engine.ingest.coingecko import CoinGeckoFetcher


@pytest.fixture()
def sample_payload() -> str:
    """Restituisce un payload CoinGecko con due giornate di osservazioni."""

    data = {
        "prices": [
            [1696170600000, 27400.0],
            [1696172400000, 27500.0],
            [1696176000000, 27600.0],
            [1696256400000, 28400.0],
            [1696260000000, 28500.0],
        ]
    }
    return json.dumps(data)


def test_coingecko_fetcher_samples_1600_cet(
    sample_payload: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Il fetcher deve campionare l'osservazione più vicina alle 16:00 CET."""

    fetcher = CoinGeckoFetcher(delay_seconds=0.0, raw_root=tmp_path)
    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: sample_payload)

    artifact = fetcher.fetch(symbols=["bitcoin"], start=pd.Timestamp("2023-09-20"))

    assert artifact.metadata["license"] == CoinGeckoFetcher.LICENSE
    assert artifact.data.shape[0] == 2

    first_row = artifact.data.iloc[0]
    second_row = artifact.data.iloc[1]

    assert first_row["date"] == pd.Timestamp("2023-10-01 15:00:00")
    assert pytest.approx(first_row["value"], rel=1e-9) == 27500.0
    assert first_row["pit_flag"] == 1

    assert second_row["date"] == pd.Timestamp("2023-10-02 15:20:00")
    assert pytest.approx(second_row["value"], rel=1e-9) == 28500.0
    assert second_row["pit_flag"] == 0

    assert artifact.data["currency"].unique().tolist() == ["EUR"]
    assert artifact.data["symbol"].unique().tolist() == ["bitcoin"]


def test_coingecko_build_url_defaults_to_five_years() -> None:
    """Senza parametro start l'URL deve coprire gli ultimi cinque anni."""

    now = datetime(2024, 1, 10, 12, 0, tzinfo=UTC)
    fetcher = CoinGeckoFetcher(delay_seconds=0.0, now_fn=lambda: now)
    url = fetcher.build_url("ethereum", None)

    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query))

    assert params["vs_currency"] == "eur"
    assert int(params["to"]) == int(now.timestamp())
    expected_from = int((now - pd.Timedelta(days=5 * 365)).timestamp())
    assert int(params["from"]) == expected_from


@pytest.mark.parametrize(
    "payload, message",
    [
        ("<html>ratelimit</html>", "HTML"),
        (json.dumps({"error": "throttle"}), "CoinGecko error"),
        (json.dumps({"foo": "bar"}), "missing 'prices'"),
    ],
)
def test_coingecko_parse_error_payload(payload: str, message: str) -> None:
    """Il parser deve fallire con messaggio chiaro su payload anomali."""

    fetcher = CoinGeckoFetcher(delay_seconds=0.0)
    with pytest.raises(ValueError, match=message):
        fetcher.parse(payload, "bitcoin")
