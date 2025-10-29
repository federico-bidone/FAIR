"""Classi base per i fetcher degli universi investibili dei broker."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Mapping

import pandas as pd


@dataclass(slots=True)
class BrokerInstrument:
    """Rappresenta uno strumento singolo reso disponibile da un broker."""

    isin: str
    name: str
    asset_class: str | None = None
    section: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BrokerUniverseArtifact:
    """Risultato strutturato restituito da :class:`BaseBrokerFetcher`."""

    broker: str
    frame: pd.DataFrame
    as_of: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)


class BaseBrokerFetcher(ABC):
    """Classe astratta da estendere per ogni fetcher di universi broker."""

    BROKER: ClassVar[str]
    SOURCE_URL: ClassVar[str]
    LICENSE: ClassVar[str | None] = None

    def __init__(self, *, session: Any | None = None) -> None:
        self._session = session

    @abstractmethod
    def fetch_universe(self) -> BrokerUniverseArtifact:
        """Scarica e interpreta l'universo investibile del broker."""

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)


__all__ = ["BaseBrokerFetcher", "BrokerInstrument", "BrokerUniverseArtifact"]
