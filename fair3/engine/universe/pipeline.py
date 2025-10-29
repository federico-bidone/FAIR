"""Pipeline che aggrega universi broker, listing OpenFIGI e provider."""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import pandas as pd

from fair3.engine.brokers import available_brokers, create_broker_fetcher

from .models import (
    InstrumentListing,
    ProviderSelection,
    UniversePipelineResult,
    build_listing_frame,
    build_provider_frame,
)
from .openfigi import OpenFIGIClient
from .providers import ProviderPreference, default_provider_preferences, select_provider

LOG = logging.getLogger(__name__)


def _first_non_null(values: Iterable[str | None]) -> str | None:
    """Restituisce la prima stringa non vuota in una sequenza, se presente."""
    for value in values:
        if value:
            return value
    return None


def run_universe_pipeline(
    *,
    brokers: Sequence[str] | None = None,
    output_dir: Path | str = Path("data") / "clean" / "universe",
    openfigi_client: OpenFIGIClient | None = None,
    openfigi_api_key: str | None = None,
    provider_preferences: Sequence[ProviderPreference] | None = None,
    broker_kwargs: Mapping[str, Mapping[str, object]] | None = None,
    dry_run: bool = False,
) -> UniversePipelineResult:
    """Orchestra il flusso completo di costruzione dell'universo investibile.

    Args:
        brokers: elenco di codici broker da processare (default: tutti quelli registrati).
        output_dir: cartella in cui persistere i Parquet e i metadati.
        openfigi_client: client già configurato per interrogare OpenFIGI.
        openfigi_api_key: chiave API da usare se occorre istanziare il client in loco.
        provider_preferences: priorità personalizzate per la scelta dei data provider.
        broker_kwargs: parametri addizionali per specifici fetcher (es. credenziali).
        dry_run: se ``True`` salta la scrittura su disco ma restituisce comunque i percorsi.

    Returns:
        :class:`UniversePipelineResult` con percorsi dei file generati e riepilogo.

    Raises:
        ValueError: se non viene indicato alcun broker da elaborare.
    """
    selected_brokers = tuple(brokers) if brokers else available_brokers()
    if not selected_brokers:
        raise ValueError("No brokers provided to the universe pipeline")

    broker_kwargs = broker_kwargs or {}
    artifacts = []
    for broker in selected_brokers:
        LOG.info("Fetching universe for broker %s", broker)
        fetcher = create_broker_fetcher(broker, **broker_kwargs.get(broker, {}))
        artifact = fetcher.fetch_universe()
        if artifact.frame.empty:
            LOG.warning("Broker %s returned an empty universe", broker)
        artifacts.append(artifact)

    frames = []
    for artifact in artifacts:
        frame = artifact.frame.copy()
        frame["broker"] = artifact.broker
        frame["as_of"] = pd.Timestamp(artifact.as_of)
        frames.append(frame)
    broker_frame = pd.concat(frames, ignore_index=True)
    broker_frame.drop_duplicates(subset=["isin", "broker"], inplace=True)
    broker_frame.sort_values(by=["broker", "isin"], inplace=True)

    unique_isins = broker_frame["isin"].dropna().unique().tolist()
    listing_map: dict[str, list[InstrumentListing]] = {}
    if unique_isins:
        client = openfigi_client
        if client is None and openfigi_api_key:
            client = OpenFIGIClient(api_key=openfigi_api_key)
        if client is not None:
            LOG.info("Querying OpenFIGI for %d unique ISINs", len(unique_isins))
            listing_map = client.map_isins(unique_isins)
        else:
            LOG.info("Skipping OpenFIGI lookup (no client provided)")

    listings: list[InstrumentListing] = []
    for isin in unique_isins:
        for listing in listing_map.get(isin, []):
            listings.append(listing)
    listing_frame = build_listing_frame(listings)

    preferences = (
        tuple(provider_preferences) if provider_preferences else default_provider_preferences()
    )
    selections: list[ProviderSelection] = []
    for isin, group in broker_frame.groupby("isin", sort=True):
        listings_for_isin = listing_map.get(isin, [])
        asset_class = _first_non_null(group["asset_class"].dropna().tolist())
        selection = select_provider(
            isin=isin,
            asset_class=asset_class,
            listings=listings_for_isin,
            preferences=preferences,
        )
        selections.append(selection)
    provider_frame = build_provider_frame(selections)

    output_path = Path(output_dir)
    metadata = {
        "instrument_count": int(broker_frame["isin"].nunique()),
        "broker_count": int(broker_frame["broker"].nunique()),
        "provider_usage": Counter(provider_frame["primary_source"]).most_common(),
    }

    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)
        broker_path = output_path / "broker_universe.parquet"
        listings_path = output_path / "instrument_listings.parquet"
        providers_path = output_path / "provider_selection.parquet"
        LOG.info("Persisting broker universe to %s", broker_path)
        broker_frame.to_parquet(broker_path)
        LOG.info("Persisting instrument listings to %s", listings_path)
        listing_frame.to_parquet(listings_path)
        LOG.info("Persisting provider selection to %s", providers_path)
        provider_frame.to_parquet(providers_path)
        metadata_path = output_path / "metadata.json"
        with metadata_path.open("w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)
    else:
        broker_path = output_path / "broker_universe.parquet"
        listings_path = output_path / "instrument_listings.parquet"
        providers_path = output_path / "provider_selection.parquet"

    as_of = max((artifact.as_of for artifact in artifacts), default=pd.Timestamp.utcnow())
    return UniversePipelineResult(
        broker_universe_path=broker_path,
        listings_path=listings_path,
        providers_path=providers_path,
        as_of=pd.Timestamp(as_of).to_pydatetime(),
        brokers=selected_brokers,
        metadata=metadata,
    )


__all__ = ["run_universe_pipeline", "UniversePipelineResult"]
