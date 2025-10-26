"""Execution decision orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionBreakdown:
    """Structured summary of an execution decision.

    Attributes:
      execute: ``True`` when all decision gates pass and trades should execute.
      drift_ok: Result of the drift-band check.
      turnover_ok: Result of the turnover constraint check.
      expected_benefit_lb: Expected benefit lower bound from the bootstrap.
      total_costs: Aggregated transaction costs for the candidate trades.
      total_taxes: Estimated tax penalty associated with the rebalance.
    """

    execute: bool
    drift_ok: bool
    turnover_ok: bool
    expected_benefit_lb: float
    total_costs: float
    total_taxes: float

    @property
    def net_benefit(self) -> float:
        """Return the net benefit after subtracting costs and taxes."""

        return self.expected_benefit_lb - self.total_costs - self.total_taxes


def should_trade(
    drift_ok: bool,
    eb_lb: float,
    cost: float,
    tax: float,
    turnover_ok: bool,
) -> bool:
    """Evaluate the EB_LB − cost − tax > 0 gate with drift and turnover checks.

    Args:
      drift_ok: Result of drift-band evaluation.
      eb_lb: Expected benefit lower bound from the bootstrap distribution.
      cost: Aggregated transaction cost for the trade list.
      tax: Estimated tax penalty.
      turnover_ok: Result of the turnover constraint evaluation.

    Returns:
      ``True`` when all constraints pass and the net benefit remains positive.
    """

    return drift_ok and turnover_ok and (eb_lb - cost - tax) > 0.0


def summarise_decision(
    drift_ok: bool,
    eb_lb: float,
    cost: float,
    tax: float,
    turnover_ok: bool,
) -> DecisionBreakdown:
    """Return a :class:`DecisionBreakdown` using :func:`should_trade`.

    Args:
      drift_ok: Result of the drift-band evaluation.
      eb_lb: Expected benefit lower bound from the bootstrap distribution.
      cost: Aggregated transaction cost for the trade list.
      tax: Estimated tax penalty.
      turnover_ok: Result of the turnover constraint evaluation.

    Returns:
      Structured decision summary including the net benefit.
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
