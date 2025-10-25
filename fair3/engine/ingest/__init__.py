"""Orchestrazione dell'ingest per FAIR-III."""

from .boe import BOEFetcher
from .ecb import ECBFetcher
from .fred import FREDFetcher
from .registry import (
    BaseCSVFetcher,
    IngestArtifact,
    available_sources,
    create_fetcher,
    run_ingest,
)
from .stooq import StooqFetcher

__all__ = [
    "BOEFetcher",
    "ECBFetcher",
    "FREDFetcher",
    "StooqFetcher",
    "BaseCSVFetcher",
    "IngestArtifact",
    "available_sources",
    "create_fetcher",
    "run_ingest",
]
