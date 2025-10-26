from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.robustness import block_bootstrap


def test_block_bootstrap_preserves_moments_within_tolerance() -> None:
    rng = np.random.default_rng(11)
    frame = pd.DataFrame(
        rng.normal(loc=0.001, scale=0.02, size=(240, 3)),
        columns=["a", "b", "c"],
    )

    samples = block_bootstrap(frame, block_size=24, n_resamples=128, seed=101)
    concatenated = pd.concat(samples, ignore_index=True)

    original_mean = frame.mean()
    original_var = frame.var(ddof=0)

    sampled_mean = concatenated.mean()
    sampled_var = concatenated.var(ddof=0)

    assert (sampled_mean - original_mean).abs().max() < 5e-3
    assert (sampled_var - original_var).abs().max() < 5e-4
