"""Euristiche per scegliere il data provider per ciascun ISIN."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import InstrumentListing, ProviderSelection


@dataclass(slots=True)
class ProviderPreference:
    """Regola di preferenza per una combinazione asset class/valuta."""

    source: str
    is_free: bool
    asset_classes: frozenset[str] | None = None
    currencies: frozenset[str] | None = None
    notes: str = ""

    def matches(self, asset_class: str | None, listings: Sequence[InstrumentListing]) -> bool:
        if self.asset_classes and (asset_class or "").title() not in self.asset_classes:
            return False
        if self.currencies:
            currencies = {listing.currency for listing in listings if listing.currency}
            if not currencies:
                return False
            if not currencies & self.currencies:
                return False
        return True


def default_provider_preferences() -> tuple[ProviderPreference, ...]:
    return (
        ProviderPreference(
            source="stooq",
            is_free=True,
            asset_classes=frozenset({"Equity", "Etf"}),
            currencies=frozenset({"EUR", "PLN", "USD"}),
            notes=(
                "Preferisci Stooq quando lo strumento azionario/ETF quota in EUR/PLN/USD "
                "e si desidera rimanere su fonti gratuite."
            ),
        ),
        ProviderPreference(
            source="yahoo",
            is_free=True,
            notes=(
                "Ripiega su Yahoo Finance quando nessuna regola specifica riesce ad assegnare "
                "un provider dedicato."
            ),
        ),
        ProviderPreference(
            source="tiingo",
            is_free=False,
            asset_classes=frozenset({"Equity", "Etf"}),
            currencies=frozenset({"USD"}),
            notes=(
                "Tiingo offre copertura USA più profonda quando è accettabile utilizzare un "
                "servizio a pagamento."
            ),
        ),
    )


def select_provider(
    *,
    isin: str,
    asset_class: str | None,
    listings: Sequence[InstrumentListing],
    preferences: Sequence[ProviderPreference],
) -> ProviderSelection:
    """Applica le preferenze per decidere da chi scaricare il prezzo dell'ISIN.

    Args:
        isin: codice ISIN oggetto della selezione.
        asset_class: asset class prevalente (se nota) raccolta dai broker.
        listings: eventuali ticker/mic già mappati da OpenFIGI.
        preferences: elenco ordinato di preferenze da valutare.

    Returns:
        Oggetto :class:`ProviderSelection` con sorgente primaria e fallback.
    """
    if not preferences:
        preferences = default_provider_preferences()
    fallback_sources = tuple(pref.source for pref in preferences)
    for pref in preferences:
        if pref.matches(asset_class, listings):
            remaining = tuple(source for source in fallback_sources if source != pref.source)
            rationale = pref.notes or f"Matched preference for {pref.source}."
            return ProviderSelection(
                isin=isin,
                primary_source=pref.source,
                is_free=pref.is_free,
                rationale=rationale,
                fallback_sources=remaining,
            )
    pref = preferences[-1]
    remaining = tuple(source for source in fallback_sources if source != pref.source)
    rationale = pref.notes or f"Defaulted to {pref.source}."
    return ProviderSelection(
        isin=isin,
        primary_source=pref.source,
        is_free=pref.is_free,
        rationale=rationale,
        fallback_sources=remaining,
    )


__all__ = ["ProviderPreference", "default_provider_preferences", "select_provider"]
