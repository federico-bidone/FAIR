from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.worldbank import WorldBankFetcher

MonkeyPatch = pytest.MonkeyPatch


def _page_payload(page: int, pages: int, values: list[tuple[str, str, float, str]]) -> str:
    """Crea payload JSON World Bank sintetico con metadati e valori."""

    metadata = {"page": page, "pages": pages, "per_page": "50"}
    entries = [
        {
            "countryiso3code": iso,
            "date": year,
            "value": value,
            "indicator": {"id": indicator},
        }
        for indicator, year, value, iso in values
    ]
    return json.dumps([metadata, entries])


def test_worldbank_fetcher_aggregates_pages(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Il fetcher unisce più pagine JSON e normalizza i simboli ISO3."""

    fetcher = WorldBankFetcher(raw_root=tmp_path)
    page_payloads = {
        "page=1": _page_payload(
            1,
            2,
            [
                ("SP.POP.TOTL", "2020", 60000000.0, "ITA"),
                ("SP.POP.TOTL", "2019", 59800000.0, "ITA"),
            ],
        ),
        "page=2": _page_payload(2, 2, [("SP.POP.TOTL", "2018", 59600000.0, "ITA")]),
    }

    def fake_download(self: WorldBankFetcher, url: str, session: object | None = None) -> str:
        for key, payload in page_payloads.items():
            if key in url:
                return payload
        raise AssertionError(f"Unexpected URL {url}")

    monkeypatch.setattr(WorldBankFetcher, "_download", fake_download)
    artifact = fetcher.fetch(symbols=["SP.POP.TOTL:ITA"], as_of=datetime.now(UTC))
    frame = artifact.data
    assert len(frame) == 3
    assert frame["symbol"].unique().tolist() == ["SP.POP.TOTL:ITA"]
    assert frame["date"].tolist() == [
        pd.Timestamp("2018-01-01"),
        pd.Timestamp("2019-01-01"),
        pd.Timestamp("2020-01-01"),
    ]
    assert pytest.approx(frame["value"].tolist()) == [59600000.0, 59800000.0, 60000000.0]
    assert artifact.metadata["license"] == WorldBankFetcher.LICENSE
    pages = {meta["page"] for meta in artifact.metadata["requests"]}
    assert pages == {1, 2}


def test_worldbank_fetcher_respects_start_filter(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Il filtro `--from` elimina le osservazioni antecedenti alla soglia richiesta."""

    fetcher = WorldBankFetcher(raw_root=tmp_path)
    payload = _page_payload(
        1,
        1,
        [
            ("NY.GDP.MKTP.KD", "2015", 2.0, "ITA"),
            ("NY.GDP.MKTP.KD", "2020", 3.0, "ITA"),
        ],
    )
    monkeypatch.setattr(
        WorldBankFetcher,
        "_download",
        lambda self, url, session=None: payload,
    )
    artifact = fetcher.fetch(symbols=["NY.GDP.MKTP.KD:ITA"], start=pd.Timestamp("2018-01-01"))
    frame = artifact.data
    assert frame["date"].tolist() == [pd.Timestamp("2020-01-01")]
    assert pytest.approx(frame["value"].tolist()) == [3.0]


def test_worldbank_build_url_requires_indicator_and_country() -> None:
    """Simboli malformati generano un errore esplicativo."""

    fetcher = WorldBankFetcher()
    with pytest.raises(ValueError, match="<indicator>:<country>"):
        fetcher.build_url("SP.POP.TOTL", None)


def test_worldbank_parse_rejects_html(tmp_path: Path) -> None:
    """Payload HTML (rate limit) vengono rigettati con ValueError."""

    fetcher = WorldBankFetcher(raw_root=tmp_path)
    with pytest.raises(ValueError, match="HTML payload"):
        fetcher.parse("<html>Error</html>", "SP.POP.TOTL:ITA")
