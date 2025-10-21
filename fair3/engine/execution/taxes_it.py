"""Simplified Italian tax heuristics for execution."""

from __future__ import annotations

import numpy as np


def tax_penalty_it(
    realized_pnl: np.ndarray,
    govies_ratio: np.ndarray,
    stamp_duty_rate: float = 0.002,
) -> float:
    """Estimate Italian-style tax penalties.

    Parameters
    ----------
    realized_pnl
        Array of realised PnL per instrument.
    govies_ratio
        Share of qualifying government securities (>=51% => 12.5% tax rate).
    stamp_duty_rate
        Pro-rata "bollo" duty rate applied to positive asset balances.

    Returns
    -------
    float
        Estimated tax penalty (capital gains + stamp duty) expressed in the same
        currency as ``realized_pnl``.
    """

    pnl = np.asarray(realized_pnl, dtype=float)
    govies_ratio = np.asarray(govies_ratio, dtype=float)
    if pnl.shape != govies_ratio.shape:
        raise ValueError("realized_pnl and govies_ratio must share the same shape")

    gains = np.maximum(pnl, 0.0)
    losses = -np.minimum(pnl, 0.0)
    govies_mask = govies_ratio >= 0.51

    other_gains = gains[~govies_mask].sum()
    govies_gains = gains[govies_mask].sum()
    loss_pool = losses.sum()

    taxable_other = max(0.0, other_gains - loss_pool)
    remaining_losses = max(0.0, loss_pool - other_gains)
    taxable_govies = max(0.0, govies_gains - remaining_losses)

    capital_gains_tax = 0.26 * taxable_other + 0.125 * taxable_govies

    stamp_base = gains.sum()
    stamp_duty = stamp_duty_rate * stamp_base

    return float(capital_gains_tax + stamp_duty)
