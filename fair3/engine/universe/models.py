"""Strutture dati condivise dalla pipeline dell'universo investibile."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd


@dataclass(slots=True)
class InstrumentListing:
    """Descrive un singolo listing/ticker ottenuto da OpenFIGI."""

    isin: str
    ticker: str | None
    mic: str | None
    currency: str | None
    exchange: str | None = None
    exch_code: str | None = None


@dataclass(slots=True)
class ProviderSelection:
    """Riepiloga la scelta del data provider per uno specifico ISIN."""

    isin: str
    primary_source: str
    is_free: bool
    rationale: str
    fallback_sources: tuple[str, ...] = ()


@dataclass(slots=True)
class UniversePipelineResult:
    """Puntatori ai file generati e metadati di sintesi."""

    broker_universe_path: Path
    listings_path: Path
    providers_path: Path
    as_of: datetime
    brokers: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


def build_listing_frame(listings: Iterable[InstrumentListing]) -> pd.DataFrame:
    """Converte una sequenza di listing in un DataFrame ordinato."""
    records = [
        {
            "isin": listing.isin,
            "ticker": listing.ticker,
            "mic": listing.mic,
            "currency": listing.currency,
            "exchange": listing.exchange,
            "exch_code": listing.exch_code,
        }
        for listing in listings
    ]
    frame = pd.DataFrame(
        records, columns=["isin", "ticker", "mic", "currency", "exchange", "exch_code"]
    )
    return frame


def build_provider_frame(selections: Iterable[ProviderSelection]) -> pd.DataFrame:
    """Trasforma le scelte dei provider in un DataFrame pronto al salvataggio."""
    records = [
        {
            "isin": selection.isin,
            "primary_source": selection.primary_source,
            "is_free": selection.is_free,
            "rationale": selection.rationale,
            "fallback_sources": ",".join(selection.fallback_sources),
        }
        for selection in selections
    ]
    frame = pd.DataFrame(
        records,
        columns=["isin", "primary_source", "is_free", "rationale", "fallback_sources"],
    )
    return frame


__all__ = [
    "InstrumentListing",
    "ProviderSelection",
    "UniversePipelineResult",
    "build_listing_frame",
    "build_provider_frame",
]
