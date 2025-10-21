import numpy as np

from fair3.engine.allocators import fit_meta_weights


def test_meta_weights_simple_case() -> None:
    returns = np.array(
        [
            [0.01, 0.008, 0.006],
            [0.012, 0.009, 0.007],
            [0.011, 0.01, 0.0065],
        ]
    )
    sigma = np.eye(3)
    weights = fit_meta_weights(returns, sigma, j_max=3, penalty_to=0.05, penalty_te=0.1)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= -1e-8)
