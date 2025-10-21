import numpy as np

from fair3.engine.allocators import (
    balance_clusters,
    generator_A,
    generator_B_hrp,
    generator_C_dro_closed,
    generator_D_cvar_erc,
)


def _toy_cov(n: int) -> np.ndarray:
    rng = np.random.default_rng(0)
    mat = rng.normal(size=(n, n))
    return mat @ mat.T + 0.1 * np.eye(n)


def test_generator_a_respects_turnover_and_sum() -> None:
    mu = np.array([0.06, 0.05, 0.04])
    sigma = _toy_cov(3)
    scenarios = np.array(
        [
            [0.01, 0.008, 0.006],
            [-0.02, -0.018, -0.015],
            [0.015, 0.01, 0.012],
        ]
    )
    constraints = {
        "scenario_returns": scenarios,
        "cvar_cap": 0.05,
        "edar_scenarios": np.abs(scenarios),
        "edar_cap": 0.10,
        "clusters": [[0, 1], [2]],
        "erc_tol": 0.05,
        "turnover_cap": 0.15,
        "w_prev": np.array([0.4, 0.4, 0.2]),
        "gross_leverage_cap": 1.2,
        "dro_rho": 0.05,
    }
    weights = generator_A(mu, sigma, constraints)
    assert np.isclose(weights.sum(), 1.0)
    turnover = 0.5 * np.sum(np.abs(weights - constraints["w_prev"]))
    assert turnover <= constraints["turnover_cap"] + 1e-6


def test_generator_b_hrp_returns_valid_weights() -> None:
    sigma = _toy_cov(4)
    weights = generator_B_hrp(sigma)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= 0)


def test_generator_c_dro_closed_simple_case() -> None:
    mu = np.array([0.05, 0.04])
    sigma = _toy_cov(2)
    weights = generator_C_dro_closed(mu, sigma, gamma=1.0, rho=0.1)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= 0)


def test_generator_d_cvar_erc_feasible() -> None:
    mu = np.array([0.05, 0.045, 0.04])
    sigma = _toy_cov(3)
    scenarios = np.array(
        [
            [0.01, 0.008, 0.006],
            [-0.015, -0.014, -0.012],
            [0.012, 0.01, 0.009],
        ]
    )
    constraints = {
        "scenario_returns": scenarios,
        "cvar_cap": 0.06,
        "clusters": [[0, 1], [2]],
        "erc_tol": 0.05,
        "turnover_cap": 0.2,
        "w_prev": np.array([0.3, 0.4, 0.3]),
        "gross_leverage_cap": 1.2,
    }
    weights = generator_D_cvar_erc(mu, sigma, constraints)
    assert np.isclose(weights.sum(), 1.0)
    assert np.all(weights >= 0)
    balanced = balance_clusters(weights, sigma, constraints["clusters"], constraints["erc_tol"])
    assert np.isclose(balanced.sum(), 1.0)
