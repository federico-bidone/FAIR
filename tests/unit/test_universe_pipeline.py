"""Unit tests for the investable universe pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pytest import MonkeyPatch

from fair3.engine.brokers.base import BaseBrokerFetcher, BrokerUniverseArtifact
from fair3.engine.universe.models import InstrumentListing
from fair3.engine.universe.pipeline import run_universe_pipeline


class _StubFetcher(BaseBrokerFetcher):
    BROKER = "stub"
    SOURCE_URL = "https://example.invalid/universe.pdf"

    def __init__(self, frame: pd.DataFrame, *, as_of: datetime) -> None:
        super().__init__()
        self._frame = frame
        self._as_of = as_of

    def fetch_universe(self) -> BrokerUniverseArtifact:
        return BrokerUniverseArtifact(
            broker=self.BROKER,
            frame=self._frame.copy(),
            as_of=self._as_of,
            metadata={"stub": True},
        )


def test_run_universe_pipeline_aggregates(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    as_of = datetime(2024, 1, 1, tzinfo=UTC)
    broker_frames = {
        "broker_a": pd.DataFrame(
            [
                {
                    "isin": "IE00B0M62Q58",
                    "name": "Vanguard FTSE All-World UCITS ETF",
                    "section": "ETF",
                    "asset_class": "ETF",
                }
            ]
        ),
        "broker_b": pd.DataFrame(
            [
                {
                    "isin": "IT0003128367",
                    "name": "Enel S.p.A.",
                    "section": "Stocks",
                    "asset_class": "Equity",
                }
            ]
        ),
    }

    class BrokerAFetcher(_StubFetcher):
        BROKER = "broker_a"

        def __init__(self) -> None:
            super().__init__(broker_frames[self.BROKER], as_of=as_of)

    class BrokerBFetcher(_StubFetcher):
        BROKER = "broker_b"

        def __init__(self) -> None:
            super().__init__(broker_frames[self.BROKER], as_of=as_of)

    def fake_fetcher_map() -> dict[str, type[BaseBrokerFetcher]]:
        return {
            "broker_a": BrokerAFetcher,
            "broker_b": BrokerBFetcher,
        }

    from fair3.engine.brokers import registry

    monkeypatch.setattr(registry, "_fetcher_map", fake_fetcher_map)

    class DummyOpenFIGI:
        def map_isins(self, isins: list[str]) -> dict[str, list[InstrumentListing]]:
            return {
                "IE00B0M62Q58": [
                    InstrumentListing(
                        isin="IE00B0M62Q58",
                        ticker="VWRL",
                        mic="XLON",
                        currency="GBP",
                        exchange="London Stock Exchange",
                        exch_code="XLON",
                    )
                ],
                "IT0003128367": [
                    InstrumentListing(
                        isin="IT0003128367",
                        ticker="ENEL",
                        mic="XMIL",
                        currency="EUR",
                        exchange="Borsa Italiana",
                        exch_code="MTAA",
                    )
                ],
            }

    result = run_universe_pipeline(
        output_dir=tmp_path,
        openfigi_client=DummyOpenFIGI(),
    )

    assert set(result.brokers) == {"broker_a", "broker_b"}
    assert result.metadata["instrument_count"] == 2
    assert result.metadata["provider_usage"]
    provider_frame = pd.read_parquet(result.providers_path)
    assert sorted(provider_frame["isin"].tolist()) == ["IE00B0M62Q58", "IT0003128367"]
