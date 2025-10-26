"""Transaction cost modelling primitives."""

from __future__ import annotations

import numpy as np


def almgren_chriss_cost(
    order_qty: np.ndarray,
    price: np.ndarray,
    spread: np.ndarray,
    adv: np.ndarray,
    eta: np.ndarray,
    fees: np.ndarray | float = 0.0,
) -> float:
    """Estimate total Almgren–Chriss transaction costs.

    Args:
      order_qty: Executed quantity per instrument. Positive values indicate buys
        and negative values indicate sells.
      price: Execution price per instrument.
      spread: Bid-ask spread expressed in price units.
      adv: Average daily volume per instrument used to scale impact.
      eta: Impact coefficient per instrument controlling nonlinear costs.
      fees: Optional explicit fees per instrument. Scalars broadcast across all
        instruments.

    Returns:
      Total transaction cost as a float combining explicit fees, half-spread
      slippage, and Almgren–Chriss impact with exponent ``1.5``.

    Raises:
      ValueError: If the provided arrays do not share the same shape.
    """

    price = np.asarray(price, dtype=float)
    spread = np.asarray(spread, dtype=float)
    order_qty = np.asarray(order_qty, dtype=float)
    adv = np.asarray(adv, dtype=float)
    eta = np.asarray(eta, dtype=float)
    fees_arr = np.asarray(fees, dtype=float)

    shapes = {arr.shape for arr in (price, spread, order_qty, adv, eta)}
    if len(shapes) != 1:
        raise ValueError("order_qty, price, spread, adv, and eta must share the same shape")

    if fees_arr.shape not in ({()}, price.shape):
        raise ValueError("fees must be scalar or share the same shape as order_qty")

    qty = np.abs(order_qty)
    half_spread = 0.5 * price * spread * qty
    with np.errstate(divide="ignore", invalid="ignore"):
        adv_ratio = np.divide(qty, adv, out=np.zeros_like(qty), where=adv > 0)
        impact = eta * np.power(adv_ratio, 1.5)

    fees_broadcast = np.broadcast_to(fees_arr, qty.shape)
    total = fees_broadcast + half_spread + impact
    return float(total.sum())


def trading_costs(
    prices: np.ndarray,
    spreads: np.ndarray,
    q: np.ndarray,
    fees: np.ndarray,
    adv: np.ndarray,
    eta: np.ndarray,
) -> np.ndarray:
    """Compute Almgren–Chriss style trading costs per instrument.

    Args:
      prices: Execution price per instrument.
      spreads: Bid-ask spread per instrument in price units.
      q: Executed quantity per instrument.
      fees: Explicit fees per instrument.
      adv: Average daily volume used to scale market impact.
      eta: Impact coefficient per instrument.

    Returns:
      Array of total costs per instrument including fees, half-spread, and
      impact.

    Raises:
      ValueError: If the provided arrays do not share the same shape.
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
        adv_ratio = np.divide(qty, adv, out=np.zeros_like(qty), where=adv > 0)
        impact = eta * np.power(adv_ratio, 1.5)

    return fees + half_spread_cost + impact
