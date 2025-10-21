"""Meta-learner combining generator outputs."""

from __future__ import annotations

import math

import cvxpy as cp
import numpy as np


def fit_meta_weights(
    returns_by_gen: np.ndarray,
    sigma_matrix: np.ndarray,
    j_max: int,
    penalty_to: float,
    penalty_te: float,
    baseline_idx: int = 0,
) -> np.ndarray:
    """Return convex combination of generator returns."""

    sigma = np.asarray(sigma_matrix, dtype=float)
    returns_matrix = np.asarray(returns_by_gen, dtype=float)
    if returns_matrix.ndim != 2:
        raise ValueError("returns_by_gen must be 2D")
    if returns_matrix.shape[1] == 0:
        return np.array([])

    n_generators = min(returns_matrix.shape[1], int(max(1, j_max)))
    returns_matrix = returns_matrix[:, :n_generators]
    cov_hat = (
        np.cov(returns_matrix, rowvar=False)
        if returns_matrix.shape[0] > 1
        else np.eye(n_generators)
    )
    cov_hat = cov_hat + 1e-6 * np.eye(n_generators)
    mu_hat = np.mean(returns_matrix, axis=0)

    baseline = np.zeros(n_generators)
    baseline[min(int(baseline_idx), n_generators - 1)] = 1.0

    alpha = cp.Variable(n_generators, nonneg=True)
    penalties = []
    if penalty_to > 0:
        penalties.append(penalty_to * 0.5 * cp.norm1(alpha - baseline))
    if penalty_te > 0:
        scale_te = math.sqrt(float(np.trace(sigma))) if sigma.ndim == 2 and sigma.size > 0 else 1.0
        penalties.append(penalty_te * scale_te * cp.norm(alpha - baseline, 2))
    risk_penalty = 0.5 * cp.quad_form(alpha, cov_hat)
    objective = cp.Maximize(mu_hat @ alpha - risk_penalty - sum(penalties))
    cons = [cp.sum(alpha) == 1.0]

    problem = cp.Problem(objective, cons)
    try:
        problem.solve(solver=cp.SCS, verbose=False, max_iters=10_000)
    except cp.SolverError:
        problem.solve(solver=cp.ECOS, verbose=False)

    if alpha.value is None:
        sol = np.full(n_generators, 1.0 / n_generators)
    else:
        sol = np.clip(np.asarray(alpha.value, dtype=float), 0.0, None)
    s = float(np.sum(sol))
    return sol / s if s > 0 else np.full(n_generators, 1.0 / n_generators)
