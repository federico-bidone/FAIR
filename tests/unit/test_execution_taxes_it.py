from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from fair3.engine.execution import (
    MinusBag,
    MinusLot,
    TaxRules,
    compute_tax_penalty,
)


def _base_inventory() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instrument_id": [
                "IT0001",
                "IT0001",
                "ITGOV",
                "ITGOV",
            ],
            "lot_id": ["old", "recent", "gov_old", "gov_new"],
            "quantity": [100.0, 100.0, 50.0, 50.0],
            "cost_basis": [90.0, 110.0, 95.0, 102.0],
            "acquired": [
                date(2020, 1, 2),
                date(2023, 1, 5),
                date(2020, 6, 1),
                date(2022, 1, 7),
            ],
            "govies_share": [0.2, 0.2, 0.7, 0.7],
        }
    )


def _base_orders() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "instrument_id": ["IT0001", "ITGOV"],
            "quantity": [-100.0, -50.0],
            "price": [120.0, 110.0],
            "trade_date": [date(2024, 5, 1), date(2024, 5, 1)],
            "govies_share": [0.2, 0.7],
        }
    )


def test_compute_tax_penalty_method_selection() -> None:
    inventory = _base_inventory()
    orders = _base_orders()

    fifo_rules = TaxRules(method="fifo", portfolio_value=200_000.0)
    fifo_result = compute_tax_penalty(orders, inventory, fifo_rules)

    lifo_rules = TaxRules(method="lifo", portfolio_value=200_000.0)
    lifo_result = compute_tax_penalty(orders, inventory, lifo_rules)

    min_tax_rules = TaxRules(method="min_tax", portfolio_value=200_000.0)
    min_result = compute_tax_penalty(orders, inventory, min_tax_rules)

    expected_fifo_capital = 0.26 * 3000.0 + 0.125 * 750.0
    expected_lifo_capital = 0.26 * 1000.0 + 0.125 * 750.0

    assert pytest.approx(fifo_result.capital_gains_tax) == expected_fifo_capital
    assert pytest.approx(lifo_result.capital_gains_tax) == expected_lifo_capital
    assert pytest.approx(min_result.capital_gains_tax) == expected_lifo_capital
    assert pytest.approx(fifo_result.taxable_other) == 3000.0
    assert pytest.approx(lifo_result.taxable_other) == 1000.0
    assert pytest.approx(min_result.taxable_other) == 1000.0
    assert pytest.approx(fifo_result.taxable_govies) == 750.0
    assert pytest.approx(lifo_result.taxable_govies) == 750.0
    assert pytest.approx(min_result.taxable_govies) == 750.0
    assert pytest.approx(fifo_result.stamp_duty) == 200_000.0 * 0.002
    assert pytest.approx(lifo_result.stamp_duty) == 200_000.0 * 0.002
    assert pytest.approx(min_result.stamp_duty) == 200_000.0 * 0.002


def test_compute_tax_penalty_consumes_minus_bag() -> None:
    inventory = _base_inventory()
    orders = _base_orders()
    bag = MinusBag([MinusLot(amount=500.0, expiry=date(2026, 1, 1))])
    rules = TaxRules(method="fifo", minus_bag=bag, portfolio_value=100_000.0)

    result = compute_tax_penalty(orders, inventory, rules)

    expected_capital = 0.26 * (3000.0 - 500.0) + 0.125 * 750.0
    assert pytest.approx(result.capital_gains_tax) == expected_capital
    assert pytest.approx(result.minus_consumed) == 500.0
    assert bag.total == pytest.approx(0.0)


def test_compute_tax_penalty_records_new_losses() -> None:
    inventory = pd.DataFrame(
        {
            "instrument_id": ["LOSS"],
            "lot_id": ["lot"],
            "quantity": [100.0],
            "cost_basis": [100.0],
            "acquired": [date(2022, 3, 1)],
            "govies_share": [0.2],
        }
    )
    orders = pd.DataFrame(
        {
            "instrument_id": ["LOSS"],
            "quantity": [-40.0],
            "price": [90.0],
            "trade_date": [date(2024, 4, 1)],
            "govies_share": [0.2],
        }
    )
    bag = MinusBag()
    rules = TaxRules(method="fifo", minus_bag=bag, portfolio_value=50_000.0)

    result = compute_tax_penalty(orders, inventory, rules)

    assert pytest.approx(result.capital_gains_tax) == 0.0
    assert pytest.approx(result.minus_added) == 400.0
    assert pytest.approx(bag.total) == 400.0


def test_compute_tax_penalty_raises_on_insufficient_inventory() -> None:
    inventory = _base_inventory()
    orders = pd.DataFrame(
        {
            "instrument_id": ["IT0001"],
            "quantity": [-300.0],
            "price": [120.0],
            "trade_date": [date(2024, 5, 1)],
            "govies_share": [0.2],
        }
    )
    rules = TaxRules(method="fifo", portfolio_value=0.0)

    with pytest.raises(ValueError):
        compute_tax_penalty(orders, inventory, rules)
