"""Lot-sizing utilities for execution."""

from __future__ import annotations

import numpy as np


def target_to_lots(
    delta_w: np.ndarray,
    portfolio_value: float,
    prices: np.ndarray,
    lot_sizes: np.ndarray,
) -> np.ndarray:
    """Convert target weight changes into integer lots.

    Parameters
    ----------
    delta_w
        Desired change in portfolio weights per instrument.
    portfolio_value
        Current portfolio market value expressed in the same currency as ``prices``.
    prices
        Latest instrument prices used to convert weight changes into units.
    lot_sizes
        Minimum tradable quantity (number of units) per instrument.

    Returns
    -------
    np.ndarray
        Integer lot counts matching the sign of ``delta_w``. Instruments with zero
        price or non-positive lot size result in zero lots.
    """

    delta_w = np.asarray(delta_w, dtype=float)
    prices = np.asarray(prices, dtype=float)
    lot_sizes = np.asarray(lot_sizes, dtype=float)

    if delta_w.shape != prices.shape or delta_w.shape != lot_sizes.shape:
        raise ValueError("delta_w, prices, and lot_sizes must share the same shape")

    if portfolio_value < 0:
        raise ValueError("Portfolio value must be non-negative")

    notional = delta_w * portfolio_value
    with np.errstate(divide="ignore", invalid="ignore"):
        units = np.divide(
            notional,
            prices,
            out=np.zeros_like(notional),
            where=prices > 0,
        )
        lots = np.divide(
            units,
            lot_sizes,
            out=np.zeros_like(units),
            where=lot_sizes > 0,
        )

    return np.rint(lots).astype(int)
