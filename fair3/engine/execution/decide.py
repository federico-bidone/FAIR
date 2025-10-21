"""Execution decision orchestration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionBreakdown:
    """Structured summary of an execution decision."""

    execute: bool
    drift_ok: bool
    turnover_ok: bool
    expected_benefit_lb: float
    total_costs: float
    total_taxes: float

    @property
    def net_benefit(self) -> float:
        return self.expected_benefit_lb - self.total_costs - self.total_taxes


def should_trade(
    drift_ok: bool,
    eb_lb: float,
    cost: float,
    tax: float,
    turnover_ok: bool,
) -> bool:
    return drift_ok and turnover_ok and (eb_lb - cost - tax) > 0.0


def summarise_decision(
    drift_ok: bool,
    eb_lb: float,
    cost: float,
    tax: float,
    turnover_ok: bool,
) -> DecisionBreakdown:
    """Return a ``DecisionBreakdown`` using :func:`should_trade`."""

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
