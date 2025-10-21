"""Transaction cost modelling."""

from __future__ import annotations

import numpy as np


def trading_costs(
    prices: np.ndarray,
    spreads: np.ndarray,
    q: np.ndarray,
    fees: np.ndarray,
    adv: np.ndarray,
    eta: np.ndarray,
) -> np.ndarray:
    """Compute Almgren–Chriss style trading costs per instrument.

    The cost formula follows ``fee + 0.5 * price * spread * |q| + eta * (|q|/ADV)^{1.5}``
    with safe handling for zero ADV inputs.
    """

    prices = np.asarray(prices, dtype=float)
    spreads = np.asarray(spreads, dtype=float)
    q = np.asarray(q, dtype=float)
    fees = np.asarray(fees, dtype=float)
    adv = np.asarray(adv, dtype=float)
    eta = np.asarray(eta, dtype=float)

    shapes = {arr.shape for arr in (prices, spreads, q, fees, adv, eta)}
    if len(shapes) != 1:
        raise ValueError("All inputs must share the same shape")

    qty = np.abs(q)
    half_spread_cost = 0.5 * prices * spreads * qty
    with np.errstate(divide="ignore", invalid="ignore"):
        adv_ratio = np.divide(
            qty,
            adv,
            out=np.zeros_like(qty),
            where=adv > 0,
        )
        impact = eta * np.power(adv_ratio, 1.5)

    return fees + half_spread_cost + impact
