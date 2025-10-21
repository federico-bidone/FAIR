"""CVaR-focused ERC allocator."""

from __future__ import annotations

from typing import Any

import cvxpy as cp
import numpy as np

from .erc import balance_clusters


def generator_D_cvar_erc(  # noqa: N802
    mu: np.ndarray,
    Sigma: np.ndarray,  # noqa: N803
    constraints: dict[str, Any],  # noqa: N803
) -> np.ndarray:
    """Minimise CVaR subject to ERC-style balancing and leverage controls."""

    mu = np.asarray(mu, dtype=float)
    sigma = np.asarray(Sigma, dtype=float)
    scenarios = np.asarray(constraints.get("scenario_returns"), dtype=float)
    if scenarios.ndim != 2 or scenarios.shape[1] != mu.size:
        raise ValueError("scenario_returns must be (T, N)")

    alpha = float(constraints.get("cvar_alpha", 0.05))
    n = mu.size
    w = cp.Variable(n, nonneg=True)
    z = cp.Variable()
    u = cp.Variable(scenarios.shape[0], nonneg=True)
    losses = -scenarios @ w
    objective = cp.Minimize(z + (1.0 / (alpha * scenarios.shape[0])) * cp.sum(u))
    cons: list[cp.constraints.constraint.Constraint] = [cp.sum(w) == 1.0, u >= losses - z]

    gross_cap = constraints.get("gross_leverage_cap")
    if gross_cap is not None:
        cons.append(cp.norm1(w) <= float(gross_cap))

    turnover_cap = constraints.get("turnover_cap")
    w_prev = constraints.get("w_prev")
    if turnover_cap is not None and w_prev is not None:
        cons.append(0.5 * cp.norm1(w - w_prev) <= float(turnover_cap))

    problem = cp.Problem(objective, cons)
    try:
        problem.solve(solver=cp.SCS, verbose=False, max_iters=10_000)
    except cp.SolverError:
        problem.solve(solver=cp.ECOS, verbose=False)
    if w.value is None:
        sol = np.full(n, 1.0 / n)
    else:
        sol = np.clip(np.asarray(w.value, dtype=float), 0.0, None)
    s = float(np.sum(sol))
    if s > 0:
        sol /= s

    clusters = constraints.get("clusters", [])
    tol = float(constraints.get("erc_tol", 0.02))
    sol = balance_clusters(sol, sigma, clusters, tol)
    sol = np.clip(sol, 0.0, None)
    total = np.sum(sol)
    return sol / total if total > 0 else np.full(n, 1.0 / n)
