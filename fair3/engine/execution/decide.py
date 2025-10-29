"""Execution decision orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionBreakdown:
    """Riepilogo strutturato di una decisione di esecuzione.

    Attributi:
      execute: ``True`` quando tutti i gate decisionali sono superati e va eseguito.
      drift_ok: Esito del controllo sulle bande di drift.
      turnover_ok: Esito del vincolo di turnover.
      expected_benefit_lb: Limite inferiore dell'expected benefit dal bootstrap.
      total_costs: Costi di transazione aggregati per i trade candidati.
      total_taxes: Penalità fiscale stimata associata al ribilanciamento.
    """

    execute: bool
    drift_ok: bool
    turnover_ok: bool
    expected_benefit_lb: float
    total_costs: float
    total_taxes: float

    @property
    def net_benefit(self) -> float:
        """Restituisce il beneficio netto al netto di costi e tasse."""

        return self.expected_benefit_lb - self.total_costs - self.total_taxes


def should_trade(
    drift_ok: bool,
    eb_lb: float,
    cost: float,
    tax: float,
    turnover_ok: bool,
) -> bool:
    """Valuta il gate EB_LB − costi − tasse > 0 con i controlli di drift e turnover.

    Args:
      drift_ok: Esito della valutazione sulle bande di drift.
      eb_lb: Limite inferiore dell'expected benefit dalla distribuzione bootstrap.
      cost: Costo di transazione aggregato per l'elenco ordini.
      tax: Penalità fiscale stimata.
      turnover_ok: Esito della valutazione sul vincolo di turnover.

    Returns:
      ``True`` quando tutti i vincoli sono rispettati e il beneficio netto resta positivo.
    """

    return drift_ok and turnover_ok and (eb_lb - cost - tax) > 0.0


def summarise_decision(
    drift_ok: bool,
    eb_lb: float,
    cost: float,
    tax: float,
    turnover_ok: bool,
) -> DecisionBreakdown:
    """Restituisce un :class:`DecisionBreakdown` usando :func:`should_trade`.

    Args:
      drift_ok: Esito della valutazione sulle bande di drift.
      eb_lb: Limite inferiore dell'expected benefit dalla distribuzione bootstrap.
      cost: Costo di transazione aggregato per l'elenco ordini.
      tax: Penalità fiscale stimata.
      turnover_ok: Esito della valutazione sul vincolo di turnover.

    Returns:
      Riepilogo decisionale strutturato che include il beneficio netto.
    """

    decision = should_trade(
        drift_ok=drift_ok,
        eb_lb=eb_lb,
        cost=cost,
        tax=tax,
        turnover_ok=turnover_ok,
    )
    return DecisionBreakdown(
        execute=decision,
        drift_ok=drift_ok,
        turnover_ok=turnover_ok,
        expected_benefit_lb=eb_lb,
        total_costs=cost,
        total_taxes=tax,
    )
