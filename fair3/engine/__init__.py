"""Namespace principale del motore FAIR-III."""

from __future__ import annotations

from . import (
    allocators,
    etl,
    factors,
    goals,
    infra,
    ingest,
    mapping,
    regime,
    reporting,
    robustness,
)

__all__ = [
    "allocators",
    "etl",
    "factors",
    "goals",
    "infra",
    "ingest",
    "mapping",
    "regime",
    "reporting",
    "robustness",
]
