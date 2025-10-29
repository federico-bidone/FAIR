from __future__ import annotations

import numpy as np


def max_trade_notional(adv: np.ndarray, prices: np.ndarray, cap_ratio: float) -> np.ndarray:
    """Restituisce il tetto nozionale imposto dai limiti ADV."""

    if cap_ratio < 0:
        raise ValueError("cap_ratio must be non-negative")
    adv_arr = np.asarray(adv, dtype=float)
    prices_arr = np.asarray(prices, dtype=float)
    if adv_arr.shape != prices_arr.shape:
        raise ValueError("adv and prices must share the same shape")
    return np.maximum(0.0, adv_arr * prices_arr * cap_ratio)


def clip_trades_to_adv(
    delta_w: np.ndarray,
    portfolio_value: float,
    adv: np.ndarray,
    prices: np.ndarray,
    cap_ratio: float,
) -> np.ndarray:
    """Ridimensiona il vettore dei trade così da non violare i limiti ADV."""

    if portfolio_value < 0:
        raise ValueError("portfolio_value must be non-negative")
    caps = max_trade_notional(adv, prices, cap_ratio)
    if portfolio_value == 0:
        return np.zeros_like(np.asarray(delta_w, dtype=float))
    delta = np.asarray(delta_w, dtype=float)
    trade_value = np.abs(delta) * portfolio_value
    limit = np.maximum(caps, 1e-12)
    scale = np.minimum(1.0, limit / np.maximum(trade_value, 1e-12))
    # preserviamo il segno
    adjusted = delta * scale
    return adjusted
