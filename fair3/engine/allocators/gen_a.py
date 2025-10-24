"""Generator A: Sharpe optimiser with scenario risk controls."""

from __future__ import annotations

import math
from typing import Any

import cvxpy as cp
import numpy as np

from .erc import balance_clusters


def _solve_problem(
    mu: np.ndarray,
    Sigma: np.ndarray,  # noqa: N803
    constraints: dict[str, Any],
) -> np.ndarray:  # noqa: N803
    n = len(mu)
    w = cp.Variable(n, nonneg=True)
    sigma_cp = 0.5 * (Sigma + Sigma.T)
    mu_vec = mu
    dro_rho = float(constraints.get("dro_rho", 0.0))
    risk_aversion = float(constraints.get("risk_aversion", 1e-4))
    objective = cp.Maximize(
        mu_vec @ w - dro_rho * cp.norm(w, 2) - risk_aversion * cp.quad_form(w, sigma_cp)
    )
    cons: list[cp.constraints.constraint.Constraint] = [cp.sum(w) == 1.0]

    gross_cap = constraints.get("gross_leverage_cap")
    if gross_cap is not None:
        cons.append(cp.norm1(w) <= float(gross_cap))

    turnover_cap = constraints.get("turnover_cap")
    w_prev = constraints.get("w_prev")
    if turnover_cap is not None and w_prev is not None:
        cons.append(0.5 * cp.norm1(w - w_prev) <= float(turnover_cap))

    scenario_returns = constraints.get("scenario_returns")
    cvar_cap = constraints.get("cvar_cap")
    if scenario_returns is not None and cvar_cap is not None:
        scenario_matrix = np.asarray(scenario_returns, dtype=float)
        alpha = float(constraints.get("cvar_alpha", 0.05))
        z = cp.Variable()
        u = cp.Variable(scenario_matrix.shape[0], nonneg=True)
        losses = -scenario_matrix @ w
        cons.extend([u >= losses - z])
        cvar = z + (1.0 / (alpha * scenario_matrix.shape[0])) * cp.sum(u)
        cons.append(cvar <= float(cvar_cap))

    edar_scenarios = constraints.get("edar_scenarios")
    edar_cap = constraints.get("edar_cap")
    if edar_scenarios is not None and edar_cap is not None:
        edar_matrix = np.asarray(edar_scenarios, dtype=float)
        beta = float(constraints.get("edar_alpha", 0.2))
        z_d = cp.Variable()
        u_d = cp.Variable(edar_matrix.shape[0], nonneg=True)
        drawdowns = edar_matrix @ w
        cons.extend([u_d >= drawdowns - z_d])
        edar = z_d + (1.0 / ((1.0 - beta) * edar_matrix.shape[0])) * cp.sum(u_d)
        cons.append(edar <= float(edar_cap))

    problem = cp.Problem(objective, cons)
    try:
        problem.solve(solver=cp.SCS, verbose=False, max_iters=10_000)
    except cp.SolverError:
        problem.solve(solver=cp.ECOS, verbose=False)
    if w.value is None:
        return np.full(n, 1.0 / n)
    sol = np.clip(np.asarray(w.value, dtype=float), 0.0, None)
    s = float(np.sum(sol))
    return sol / s if s > 0 else np.full(n, 1.0 / n)


def generator_A(  # noqa: N802
    mu: np.ndarray,
    Sigma: np.ndarray,  # noqa: N803
    constraints: dict[str, Any],
) -> np.ndarray:  # noqa: N803
    """Sharpe-driven allocator with scenario risk controls and ERC balancing."""

    mu = np.asarray(mu, dtype=float)
    sigma = np.asarray(Sigma, dtype=float)
    if mu.ndim != 1 or sigma.shape[0] != sigma.shape[1]:
        raise ValueError("mu and Sigma shapes are inconsistent")
    if sigma.shape[0] != mu.shape[0]:
        raise ValueError("Sigma dimension mismatch")

    weights = _solve_problem(mu, sigma, constraints)

    clusters = constraints.get("clusters", [])
    tol = float(constraints.get("erc_tol", 0.02))
    weights = balance_clusters(weights, sigma, clusters, tol)

    turnover_cap = constraints.get("turnover_cap")
    w_prev = constraints.get("w_prev")
    if turnover_cap is not None and w_prev is not None:
        delta = 0.5 * np.sum(np.abs(weights - np.asarray(w_prev)))
        if delta > float(turnover_cap) + 1e-6:
            scale = float(turnover_cap) / delta
            weights = np.asarray(w_prev) + scale * (weights - np.asarray(w_prev))
            weights = np.clip(weights, 0.0, None)
            s = np.sum(weights)
            if s > 0:
                weights /= s

    weights = np.clip(weights, 0.0, None)
    total = float(np.sum(weights))
    if not math.isfinite(total) or total <= 0:
        return np.full_like(weights, 1.0 / len(weights))
    return weights / total
