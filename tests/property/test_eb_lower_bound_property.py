from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.execution import expected_benefit_lower_bound


def test_eb_lower_bound_monotonic_with_positive_shift() -> None:
    rng = np.random.default_rng(17)
    returns = pd.DataFrame(
        rng.normal(loc=0.0, scale=0.01, size=(180, 3)),
        columns=["x", "y", "z"],
    )
    w_old = np.array([0.4, 0.35, 0.25])
    w_new = np.array([0.45, 0.30, 0.25])
    delta_w = w_new - w_old

    base_lb = expected_benefit_lower_bound(
        returns,
        delta_w,
        w_old,
        w_new,
        alpha=0.05,
        block_size=30,
        n_resamples=96,
        seed=222,
    )

    uplift_returns = returns + 0.0005
    uplift_lb = expected_benefit_lower_bound(
        uplift_returns,
        delta_w,
        w_old,
        w_new,
        alpha=0.05,
        block_size=30,
        n_resamples=96,
        seed=222,
    )

    assert uplift_lb >= base_lb - 1e-9
