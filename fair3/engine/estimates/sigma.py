"""Covariance estimation and smoothing utilities."""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.covariance import graphical_lasso
from sklearn.exceptions import ConvergenceWarning

from fair3.engine.utils import project_to_psd

LOG = logging.getLogger(__name__)


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


def _symmetrize(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    return 0.5 * (matrix + matrix.T)


def _matrix_from_eigendecomposition(
    matrix: NDArray[np.float64],
    transform: Callable[[NDArray[np.float64]], NDArray[np.float64]],
) -> NDArray[np.float64]:
    sym = _symmetrize(matrix)
    eigvals, eigvecs = np.linalg.eigh(sym)
    eigvals = transform(np.clip(eigvals, 1e-12, None))
    rebuilt = eigvecs @ np.diag(eigvals) @ eigvecs.T
    return _symmetrize(rebuilt)


def _matrix_power(matrix: NDArray[np.float64], power: float) -> NDArray[np.float64]:
    return _matrix_from_eigendecomposition(matrix, lambda vals: vals**power)


def _matrix_log(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    return _matrix_from_eigendecomposition(matrix, lambda vals: np.log(vals))


def _matrix_exp(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    return _matrix_from_eigendecomposition(matrix, lambda vals: np.exp(vals))


def _ensure_spd(matrix: NDArray[np.float64], min_eig: float = 1e-8) -> NDArray[np.float64]:
    sym = _symmetrize(matrix)
    eigvals, eigvecs = np.linalg.eigh(sym)
    eigvals = np.clip(eigvals, min_eig, None)
    rebuilt = eigvecs @ np.diag(eigvals) @ eigvecs.T
    return _symmetrize(rebuilt)


def _riemannian_log(base: NDArray[np.float64], target: NDArray[np.float64]) -> NDArray[np.float64]:
    base = _ensure_spd(base)
    target = _ensure_spd(target)
    base_inv_sqrt = _matrix_power(base, -0.5)
    base_sqrt = _matrix_power(base, 0.5)
    transported = base_inv_sqrt @ target @ base_inv_sqrt
    log_transport = _matrix_log(transported)
    return _symmetrize(base_sqrt @ log_transport @ base_sqrt)


def _riemannian_exp(base: NDArray[np.float64], tangent: NDArray[np.float64]) -> NDArray[np.float64]:
    base = _ensure_spd(base)
    tangent = _symmetrize(tangent)
    base_inv_sqrt = _matrix_power(base, -0.5)
    base_sqrt = _matrix_power(base, 0.5)
    transported = base_inv_sqrt @ tangent @ base_inv_sqrt
    exp_transport = _matrix_exp(transported)
    proposal = base_sqrt @ exp_transport @ base_sqrt
    return _ensure_spd(proposal)


def sigma_consensus_psd(covariances: list[pd.DataFrame]) -> pd.DataFrame:
    """Compute the PSD consensus covariance via element-wise median.

    Args:
      covariances: Covariance estimates expressed as square dataframes with the
        same index and columns ordering.

    Returns:
      Positive semidefinite covariance matrix as dataframe matching the first
      input frame's labels.

    Raises:
      ValueError: If the covariance list is empty or contains incompatible
        shapes/index alignment.
    """

    if not covariances:
        raise ValueError("At least one covariance matrix is required")
    first = covariances[0]
    arrays: list[NDArray[np.float64]] = []
    for frame in covariances:
        if frame.shape != first.shape:
            raise ValueError("All covariance matrices must share the same shape")
        if not frame.index.equals(first.index) or not frame.columns.equals(first.columns):
            raise ValueError("Covariance matrices must share identical labels")
        arrays.append(_symmetrize(frame.to_numpy(dtype=float)))
    median = median_of_covariances(arrays)
    return pd.DataFrame(median, index=first.index.copy(), columns=first.columns.copy())


def sigma_spd_median(
    covariances: list[pd.DataFrame],
    *,
    max_iter: int = 200,
    tol: float = 1e-6,
) -> pd.DataFrame:
    """Compute the geometric median of SPD covariance matrices.

    The routine performs Riemannian gradient descent on the manifold of SPD
    matrices using the affine-invariant metric. If convergence is not achieved
    within ``max_iter`` iterations, a warning is emitted and the PSD consensus
    estimate is returned instead.

    Args:
      covariances: Covariance estimates expressed as square dataframes with the
        same ordering of labels.
      max_iter: Maximum number of gradient iterations before falling back.
      tol: Convergence tolerance on the Frobenius norm of the gradient.

    Returns:
      Dataframe containing the SPD geometric median aligned with the first
      covariance frame labels.

    Raises:
      ValueError: If the covariance collection is empty or labels are
        inconsistent across inputs.
    """

    if not covariances:
        raise ValueError("At least one covariance matrix is required")
    consensus = sigma_consensus_psd(covariances)
    try:
        arrays = [_ensure_spd(frame.to_numpy(dtype=float)) for frame in covariances]
        current = _ensure_spd(consensus.to_numpy(dtype=float))
    except np.linalg.LinAlgError as exc:
        LOG.warning("SPD median input not SPD; falling back to PSD median: %s", exc)
        return consensus
    success = False
    for iteration in range(max_iter):
        gradient = np.zeros_like(current)
        for array in arrays:
            try:
                gradient += _riemannian_log(current, array)
            except np.linalg.LinAlgError as exc:
                LOG.warning("SPD median log map failed; falling back to PSD median: %s", exc)
                return consensus
        gradient /= float(len(arrays))
        grad_norm = float(np.linalg.norm(gradient, ord="fro"))
        if not np.isfinite(grad_norm):
            break
        if grad_norm <= tol:
            success = True
            break
        step = 1.0 / float(iteration + 1)
        try:
            current = _riemannian_exp(current, -step * gradient)
        except np.linalg.LinAlgError as exc:
            LOG.warning("SPD median exp map failed; falling back to PSD median: %s", exc)
            return consensus
    if not success:
        LOG.warning(
            "SPD median did not converge within max_iter=%s; falling back to PSD median",
            max_iter,
        )
        return consensus
    return pd.DataFrame(
        _symmetrize(current),
        index=consensus.index.copy(),
        columns=consensus.columns.copy(),
    )


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
    "sigma_consensus_psd",
    "sigma_spd_median",
]
