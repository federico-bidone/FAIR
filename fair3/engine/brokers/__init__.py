"""Modulo di comodo che espone i fetcher degli universi broker di FAIR-III."""

from .base import BaseBrokerFetcher, BrokerInstrument, BrokerUniverseArtifact
from .registry import available_brokers, create_broker_fetcher
from .trade_republic import TradeRepublicFetcher

__all__ = [
    "BaseBrokerFetcher",
    "BrokerInstrument",
    "BrokerUniverseArtifact",
    "TradeRepublicFetcher",
    "available_brokers",
    "create_broker_fetcher",
]
