from __future__ import annotations

import numpy as np
import pytest

from fair3.engine.execution import (
    DecisionBreakdown,
    drift_bands_exceeded,
    expected_benefit,
    summarise_decision,
    target_to_lots,
    tax_penalty_it,
    trading_costs,
)


def test_target_to_lots_rounds_and_handles_zero_inputs() -> None:
    delta_w = np.array([0.02, -0.01, 0.001])
    lots = target_to_lots(
        delta_w,
        portfolio_value=1_000_000.0,
        prices=np.array([50.0, 100.0, 0.0]),
        lot_sizes=np.array([10.0, 5.0, 1.0]),
    )
    assert np.array_equal(lots, np.array([40, -20, 0]))


def test_trading_costs_matches_formula() -> None:
    prices = np.array([100.0, 50.0])
    spreads = np.array([0.01, 0.02])
    q = np.array([200.0, -150.0])
    fees = np.array([5.0, 7.5])
    adv = np.array([10_000.0, 0.0])
    eta = np.array([0.25, 0.10])

    costs = trading_costs(prices, spreads, q, fees, adv, eta)

    expected = np.array(
        [
            5.0 + 0.5 * 100.0 * 0.01 * 200.0 + 0.25 * (200.0 / 10_000.0) ** 1.5,
            7.5 + 0.5 * 50.0 * 0.02 * 150.0 + 0.10 * 0.0,
        ]
    )
    assert np.allclose(costs, expected)


def test_tax_penalty_it_applies_rates_and_loss_bucket() -> None:
    pnl = np.array([500.0, 200.0, -300.0])
    govies_ratio = np.array([0.2, 0.6, 0.0])
    penalty = tax_penalty_it(pnl, govies_ratio)

    other_gains = 500.0
    govies_gains = 200.0
    losses = 300.0
    taxable_other = max(0.0, other_gains - losses)
    remaining_loss = max(0.0, losses - other_gains)
    taxable_govies = max(0.0, govies_gains - remaining_loss)
    expected_tax = 0.26 * taxable_other + 0.125 * taxable_govies
    stamp_duty = 0.002 * (other_gains + govies_gains)

    assert pytest.approx(penalty) == expected_tax + stamp_duty


def test_drift_bands_and_expected_benefit() -> None:
    w_old = np.array([0.5, 0.5])
    w_new = np.array([0.6, 0.4])
    rc_old = w_old.copy()
    rc_new = w_new.copy()
    band = 0.05
    assert drift_bands_exceeded(w_old, w_new, rc_old, rc_new, band) is True

    mu = np.array([0.08, 0.04])
    sigma = np.array([[0.04, 0.01], [0.01, 0.03]])
    delta_w = w_new - w_old
    eb = expected_benefit(delta_w, mu, sigma, w_old, w_new)

    mu_old = float(w_old @ mu)
    mu_new = float(w_new @ mu)
    var_old = float(w_old @ sigma @ w_old)
    var_new = float(w_new @ sigma @ w_new)
    expected = (mu_new - mu_old) - 0.5 * (var_new - var_old)
    assert pytest.approx(eb) == expected


def test_summarise_decision_structures_breakdown() -> None:
    breakdown = summarise_decision(
        drift_ok=True,
        eb_lb=0.03,
        cost=0.01,
        tax=0.005,
        turnover_ok=False,
    )
    assert isinstance(breakdown, DecisionBreakdown)
    assert breakdown.execute is False
    assert pytest.approx(breakdown.net_benefit) == 0.015
