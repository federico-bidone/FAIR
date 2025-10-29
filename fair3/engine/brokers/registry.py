"""Registro centralizzato dei fetcher degli universi broker."""

from __future__ import annotations

from typing import Mapping

from .base import BaseBrokerFetcher
from .trade_republic import TradeRepublicFetcher


def _fetcher_map() -> Mapping[str, type[BaseBrokerFetcher]]:
    """Mappa il codice del broker alla relativa classe fetcher."""
    return {
        TradeRepublicFetcher.BROKER: TradeRepublicFetcher,
    }


def available_brokers() -> tuple[str, ...]:
    """Restituisce l'elenco ordinato dei broker supportati nativamente."""
    return tuple(sorted(_fetcher_map().keys()))


def create_broker_fetcher(broker: str, **kwargs: object) -> BaseBrokerFetcher:
    """Istanzia il fetcher associato al broker richiesto.

    Args:
        broker: identificativo del broker (chiave restituita da :func:`available_brokers`).
        **kwargs: parametri specifici da inoltrare al costruttore del fetcher.

    Returns:
        Istanza di :class:`BaseBrokerFetcher` pronta per l'uso.

    Raises:
        ValueError: se il broker richiesto non è registrato.
    """
    try:
        fetcher_cls = _fetcher_map()[broker]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unsupported broker '{broker}'. Known: {available_brokers()}") from exc
    return fetcher_cls(**kwargs)


__all__ = ["available_brokers", "create_broker_fetcher"]
