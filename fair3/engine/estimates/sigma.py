"""Covariance estimation and smoothing utilities."""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.covariance import graphical_lasso
from sklearn.exceptions import ConvergenceWarning

from fair3.engine.utils import project_to_psd


@dataclass
class GraphicalLassoResult:
    covariance: NDArray[np.float64]
    precision: NDArray[np.float64]
    alpha: float
    bic: float


def _validate_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("Input dataframe must not be empty")
    if frame.isna().any().any():
        raise ValueError("Input dataframe contains NaNs")
    return frame


def ledoit_wolf(frame: pd.DataFrame) -> NDArray[np.float64]:
    """Estimate a Ledoit–Wolf shrinkage covariance matrix."""

    from sklearn.covariance import LedoitWolf

    frame = _validate_frame(frame)
    model = LedoitWolf(assume_centered=False)
    covariance = model.fit(frame.to_numpy(dtype=float)).covariance_
    return project_to_psd(np.asarray(covariance, dtype=float))


def _graphical_lasso_path(
    emp_cov: NDArray[np.float64],
    lambdas: Iterable[float],
    n_samples: int,
) -> list[GraphicalLassoResult]:
    results: list[GraphicalLassoResult] = []
    for alpha in lambdas:
        if alpha <= 0:
            continue
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            covariance, precision = graphical_lasso(emp_cov, alpha=alpha, max_iter=200, tol=1e-4)
        sign, logdet = np.linalg.slogdet(precision)
        if sign <= 0:
            continue
        log_likelihood = n_samples * (logdet - np.trace(emp_cov @ precision))
        non_zero = np.count_nonzero(np.triu(precision))
        bic = -2.0 * log_likelihood + non_zero * np.log(n_samples)
        results.append(
            GraphicalLassoResult(
                covariance=np.asarray(covariance, dtype=float),
                precision=np.asarray(precision, dtype=float),
                alpha=float(alpha),
                bic=float(bic),
            )
        )
    return results


def graphical_lasso_bic(
    frame: pd.DataFrame,
    lambdas: list[float] | None = None,
    cv_split_id: int | None = None,
    random_state: int | None = None,
) -> NDArray[np.float64]:
    """Select the graphical lasso covariance via BIC scoring.

    ``cv_split_id`` and ``random_state`` are accepted to provide deterministic
    shuffling of the candidate lambda grid when cross-validation pipelines invoke
    this routine repeatedly.
    """

    frame = _validate_frame(frame)
    if lambdas is None:
        lambdas = [0.01, 0.025, 0.05, 0.075, 0.1]
    if random_state is not None:
        rng = np.random.default_rng(random_state + (cv_split_id or 0))
        lambdas = list(lambdas)
        rng.shuffle(lambdas)
    centered = frame.to_numpy(dtype=float)
    centered -= centered.mean(axis=0, keepdims=True)
    n_samples = centered.shape[0]
    if n_samples < 2:
        raise ValueError("Need at least two samples for covariance estimation")
    emp_cov = np.cov(centered, rowvar=False, bias=False)
    path = _graphical_lasso_path(emp_cov, lambdas, n_samples)
    if not path:
        raise RuntimeError("Graphical lasso failed to converge for all lambdas")
    best = min(path, key=lambda res: res.bic)
    return project_to_psd(best.covariance)


def factor_shrink(frame: pd.DataFrame, n_factors: int | None = None) -> NDArray[np.float64]:
    """Shrink the sample covariance towards a factor model approximation."""

    frame = _validate_frame(frame)
    values = frame.to_numpy(dtype=float)
    values -= values.mean(axis=0, keepdims=True)
    n_samples, n_assets = values.shape
    if n_samples < 2:
        raise ValueError("Need at least two samples for covariance estimation")
    sample = np.cov(values, rowvar=False, bias=False)
    if n_factors is None:
        n_factors = max(1, min(5, n_assets, n_samples - 1))
    eigvals, eigvecs = np.linalg.eigh(sample)
    idx = np.argsort(eigvals)[::-1]
    eigvals = eigvals[idx]
    eigvecs = eigvecs[:, idx]
    k = min(n_factors, len(eigvals))
    leading = eigvecs[:, :k]
    leading_vals = np.clip(eigvals[:k], 0.0, None)
    factor_cov = (leading * leading_vals) @ leading.T
    specific = np.diag(np.clip(np.diag(sample - factor_cov), 1e-8, None))
    shrunk = factor_cov + specific
    return project_to_psd(shrunk)


def median_of_covariances(covs: list[NDArray[np.float64]]) -> NDArray[np.float64]:
    """Compute the element-wise median of covariance matrices."""

    if not covs:
        raise ValueError("At least one covariance matrix is required")
    stacked = np.stack(covs, axis=0)
    if stacked.ndim != 3 or stacked.shape[1] != stacked.shape[2]:
        raise ValueError("Covariance matrices must be square")
    median = np.median(stacked, axis=0)
    return project_to_psd(median)


def ewma_regime(
    sigma_prev: NDArray[np.float64],
    sigma_star_psd: NDArray[np.float64],
    lambda_r: float,
) -> NDArray[np.float64]:
    """Blend previous and current covariances with EWMA weighting and PSD projection."""

    if not 0.0 <= lambda_r <= 1.0:
        raise ValueError("lambda_r must be within [0, 1]")
    if sigma_prev.shape != sigma_star_psd.shape:
        raise ValueError("Covariances must share the same shape")
    blended = lambda_r * sigma_prev + (1.0 - lambda_r) * sigma_star_psd
    return project_to_psd(blended)


__all__ = [
    "GraphicalLassoResult",
    "ewma_regime",
    "factor_shrink",
    "graphical_lasso_bic",
    "ledoit_wolf",
    "median_of_covariances",
]
