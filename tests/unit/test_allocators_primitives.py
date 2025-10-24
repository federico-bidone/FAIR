import numpy as np

from fair3.engine.allocators import (
    dro_penalty,
    risk_contributions,
    sharpe_objective,
)


def test_risk_contributions_sum_to_one() -> None:
    sigma = np.array([[0.04, 0.01], [0.01, 0.09]])
    w = np.array([0.6, 0.4])
    rc = risk_contributions(w, sigma)
    assert np.isclose(rc.sum(), 1.0)


def test_sharpe_objective_positive() -> None:
    sigma = np.array([[0.02, 0.0], [0.0, 0.03]])
    mu = np.array([0.05, 0.03])
    w = np.array([0.5, 0.5])
    sharpe = sharpe_objective(w, mu, sigma)
    assert sharpe > 0


def test_dro_penalty_non_negative() -> None:
    w = np.array([0.4, 0.6])
    penalty = dro_penalty(w, rho=0.2)
    assert penalty >= 0
