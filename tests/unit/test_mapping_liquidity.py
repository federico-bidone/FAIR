from __future__ import annotations

import numpy as np

from fair3.engine.mapping import clip_trades_to_adv, max_trade_notional


def test_max_trade_notional_scales_adv() -> None:
    adv = np.array([1000.0, 500.0])
    prices = np.array([50.0, 20.0])
    cap = 0.05
    caps = max_trade_notional(adv, prices, cap)
    expected = adv * prices * cap
    np.testing.assert_allclose(caps, expected)


def test_clip_trades_to_adv_limits_notional() -> None:
    delta_w = np.array([0.2, -0.1])
    portfolio_value = 200_000.0
    adv = np.array([5_000.0, 2_500.0])
    prices = np.array([40.0, 30.0])
    cap = 0.05
    adjusted = clip_trades_to_adv(delta_w, portfolio_value, adv, prices, cap)
    caps = max_trade_notional(adv, prices, cap)
    trade_value = np.abs(adjusted) * portfolio_value
    assert np.all(trade_value <= caps + 1e-8)
    # Il segno dei trade viene preservato
    assert np.all(np.sign(adjusted) == np.sign(delta_w))
