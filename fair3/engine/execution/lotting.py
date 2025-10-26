"""Lot-sizing utilities for execution."""

from __future__ import annotations

import numpy as np


def size_orders(
    delta_w: np.ndarray,
    portfolio_value: float,
    prices: np.ndarray,
    lot_sizes: np.ndarray,
) -> np.ndarray:
    """Convert weight deltas into integer lot counts.

    Args:
      delta_w: Desired change in portfolio weights per instrument expressed as
        fractions of portfolio value.
      portfolio_value: Current portfolio value expressed in the same currency as
        ``prices``.
      prices: Latest instrument prices. Zero or negative prices disable trading
        for the corresponding instrument.
      lot_sizes: Minimum tradable quantity per instrument. Non-positive lot sizes
        disable trading for the corresponding instrument.

    Returns:
      Integer array containing the number of lots to trade for each instrument.
      The sign follows ``delta_w`` and instruments with invalid pricing or lot
      constraints return zero.

    Raises:
      ValueError: If the input arrays have mismatched shapes or the portfolio
        value is negative.
    """

    delta_w = np.asarray(delta_w, dtype=float)
    prices = np.asarray(prices, dtype=float)
    lot_sizes = np.asarray(lot_sizes, dtype=float)

    if delta_w.shape != prices.shape or delta_w.shape != lot_sizes.shape:
        raise ValueError("delta_w, prices, and lot_sizes must share the same shape")

    if portfolio_value < 0:
        raise ValueError("portfolio_value must be non-negative")

    notional = delta_w * portfolio_value
    with np.errstate(divide="ignore", invalid="ignore"):
        denominator = prices * lot_sizes
        lots = np.divide(
            notional,
            denominator,
            out=np.zeros_like(notional),
            where=(prices > 0) & (lot_sizes > 0),
        )

    return np.rint(lots).astype(int)


def target_to_lots(
    delta_w: np.ndarray,
    portfolio_value: float,
    prices: np.ndarray,
    lot_sizes: np.ndarray,
) -> np.ndarray:
    """Alias for :func:`size_orders` kept for backward compatibility."""

    return size_orders(delta_w, portfolio_value, prices, lot_sizes)
