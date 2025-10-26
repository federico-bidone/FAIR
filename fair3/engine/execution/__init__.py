"""Execution helpers for FAIR-III."""

from .costs import almgren_chriss_cost, trading_costs
from .decide import DecisionBreakdown, should_trade, summarise_decision
from .lotting import size_orders, target_to_lots
from .taxes_it import (
    MinusBag,
    MinusLot,
    TaxComputation,
    TaxRules,
    compute_tax_penalty,
    tax_penalty_it,
)
from .trade_rules import (
    drift_bands_exceeded,
    expected_benefit,
    expected_benefit_distribution,
    expected_benefit_lower_bound,
)

__all__ = [
    "DecisionBreakdown",
    "drift_bands_exceeded",
    "expected_benefit",
    "expected_benefit_distribution",
    "expected_benefit_lower_bound",
    "almgren_chriss_cost",
    "compute_tax_penalty",
    "MinusBag",
    "MinusLot",
    "should_trade",
    "summarise_decision",
    "size_orders",
    "target_to_lots",
    "tax_penalty_it",
    "trading_costs",
    "TaxComputation",
    "TaxRules",
]
