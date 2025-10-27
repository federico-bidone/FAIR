"""Beta estimation utilities for the mapping pipeline."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from fair3.engine.utils.rand import generator_from_seed

_STREAM_BOOT = "mapping.beta_bootstrap"


def _prepare_frames(
    returns: pd.DataFrame, factors: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Index]:
    """Align return and factor frames on their common date index.

    Args:
      returns: Instrument returns indexed by ``DatetimeIndex``.
      factors: Factor returns indexed by ``DatetimeIndex``.

    Returns:
      Tuple containing aligned returns, aligned factors, and the shared index.

    Raises:
      ValueError: If the aligned data produces no observations.
    """

    common = returns.index.intersection(factors.index)
    if common.empty:
        raise ValueError("returns and factors must share a non-empty index")
    ret = returns.loc[common].sort_index()
    fac = factors.loc[common].sort_index()
    combined = ret.join(fac, how="inner").dropna(how="any")
    if combined.empty:
        raise ValueError("returns and factors alignment produced no rows")
    ret_aligned = combined[returns.columns]
    fac_aligned = combined[factors.columns]
    return ret_aligned, fac_aligned, combined.index


def _enforce_signs(
    values: np.ndarray,
    factors: Iterable[str],
    sign: dict[str, int],
    enforce_sign: bool,
) -> None:
    """Apply optional sign constraints to beta estimates in-place.

    Args:
      values: Matrix of factor loadings with shape (n_factors, n_assets).
      factors: Iterable of factor identifiers corresponding to the rows of
        ``values``.
      sign: Mapping from factor name to expected sign (+1 or -1).
      enforce_sign: Flag controlling whether the constraints are applied.
    """

    if not enforce_sign or not sign:
        return
    for j, factor in enumerate(factors):
        desired = sign.get(factor)
        if desired == 1:
            values[j, :] = np.maximum(values[j, :], 0.0)
        elif desired == -1:
            values[j, :] = np.minimum(values[j, :], 0.0)


def _solve_ridge(xtx: np.ndarray, xty: np.ndarray) -> np.ndarray:
    """Solve ridge-regularised normal equations in a numerically stable way.

    Args:
      xtx: Symmetric factor scatter matrix with ridge penalty applied.
      xty: Cross-product between centred factors and centred returns.

    Returns:
      Estimated loadings matrix solving the normal equations.
    """

    try:
        return np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(xtx) @ xty


def rolling_beta_ridge(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    window: int,
    lambda_beta: float,
    sign_prior: dict[str, int] | None = None,
    enforce_sign: bool = True,
) -> pd.DataFrame:
    """Estimate rolling ridge betas with optional economic sign priors.

    Args:
      returns: Panel of instrument returns.
      factors: Panel of factor returns aligned with ``returns``.
      window: Rolling window length (number of observations).
      lambda_beta: Ridge penalty added to the factor scatter matrix.
      sign_prior: Mapping of factor name to expected sign (+1 or -1).
      enforce_sign: Whether to enforce the sign priors during estimation.

    Returns:
      DataFrame of rolling betas indexed by date and multi-indexed by instrument
      and factor.

    Raises:
      ValueError: If ``window`` or ``lambda_beta`` are invalid or the aligned
        dataset lacks sufficient rows.
    """

    if window <= 1:
        raise ValueError("window must be greater than one")
    if lambda_beta < 0:
        raise ValueError("lambda_beta must be non-negative")
    sign_dict = dict(sign_prior or {})
    ret, fac, index = _prepare_frames(returns, factors)
    n_obs, n_assets = ret.shape
    n_factors = fac.shape[1]
    if n_obs < window:
        raise ValueError("window exceeds available observations")

    columns = pd.MultiIndex.from_product([ret.columns, fac.columns], names=["instrument", "factor"])
    betas = pd.DataFrame(np.nan, index=index, columns=columns, dtype=float)

    eye = np.eye(n_factors)
    factors_values = fac.to_numpy()
    returns_values = ret.to_numpy()

    for pos in range(window - 1, n_obs):
        rows = slice(pos - window + 1, pos + 1)
        window_factors = factors_values[rows]
        window_returns = returns_values[rows]
        factors_centered = window_factors - window_factors.mean(axis=0, keepdims=True)
        returns_centered = window_returns - window_returns.mean(axis=0, keepdims=True)
        xtx = factors_centered.T @ factors_centered + lambda_beta * eye
        xty = factors_centered.T @ returns_centered
        beta_window = _solve_ridge(xtx, xty)
        _enforce_signs(beta_window, fac.columns, sign_dict, enforce_sign)
        betas.iloc[pos] = beta_window.T.reshape(-1)

    betas.attrs["window"] = window
    betas.attrs["ridge_lambda"] = float(lambda_beta)
    if sign_dict:
        betas.attrs["sign_constraints"] = sign_dict
    betas.attrs["enforce_sign"] = bool(enforce_sign)
    return betas


def beta_ci_bootstrap(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    beta_ts: pd.DataFrame,
    B: int = 1000,  # noqa: N803
    alpha: float = 0.2,
) -> pd.DataFrame:
    """Estimate bootstrap confidence intervals for rolling betas.

    Args:
      returns: Instrument return panel.
      factors: Factor panel aligned with ``returns``.
      beta_ts: Rolling beta time series from :func:`rolling_beta_ridge`.
      B: Number of bootstrap draws per window.
      alpha: Two-sided significance level (e.g., 0.2 for CI80).

    Returns:
      DataFrame indexed by date with MultiIndex columns
      (instrument, factor, bound).

    Raises:
      ValueError: If bootstrap parameters are invalid or indices misalign.
    """

    if B <= 0:
        raise ValueError("B must be positive")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be between 0 and 1")

    ret, fac, index = _prepare_frames(returns, factors)
    betas = beta_ts.loc[index]
    valid = betas.dropna(how="all")
    if valid.empty:
        raise ValueError("beta_ts does not contain any finite rows")
    first_idx = valid.index[0]
    try:
        start_pos = index.get_loc(first_idx)
    except KeyError as exc:
        raise ValueError("beta_ts index must align with returns/factors") from exc

    window = int(beta_ts.attrs.get("window", start_pos + 1))
    window = max(window, 1)
    lambda_beta = float(beta_ts.attrs.get("ridge_lambda", 0.0))
    sign_dict: dict[str, int] = dict(beta_ts.attrs.get("sign_constraints", {}))
    enforce_sign = bool(beta_ts.attrs.get("enforce_sign", True))

    n_obs, n_assets = ret.shape
    n_factors = fac.shape[1]
    eye = np.eye(n_factors)
    lower_q = alpha / 2
    upper_q = 1.0 - alpha / 2

    columns = pd.MultiIndex.from_product(
        [ret.columns, fac.columns, ["lower", "upper"]],
        names=["instrument", "factor", "bound"],
    )
    ci = pd.DataFrame(np.nan, index=index, columns=columns, dtype=float)

    rng = generator_from_seed(stream=_STREAM_BOOT)
    fac_values = fac.to_numpy()
    ret_values = ret.to_numpy()

    for pos in range(start_pos, n_obs):
        if pos + 1 < window:
            continue
        current = betas.iloc[pos]
        if current.isna().all():
            continue
        rows = slice(pos - window + 1, pos + 1)
        window_factors = fac_values[rows]
        window_returns = ret_values[rows]
        factors_centered = window_factors - window_factors.mean(axis=0, keepdims=True)
        returns_centered = window_returns - window_returns.mean(axis=0, keepdims=True)
        samples = np.empty((B, n_assets * n_factors), dtype=float)
        for b in range(B):
            picks = rng.integers(0, window, size=window)
            sampled_factors = factors_centered[picks]
            sampled_returns = returns_centered[picks]
            xtx = sampled_factors.T @ sampled_factors + lambda_beta * eye
            xty = sampled_factors.T @ sampled_returns
            beta_sample = _solve_ridge(xtx, xty)
            _enforce_signs(beta_sample, fac.columns, sign_dict, enforce_sign)
            samples[b] = beta_sample.T.reshape(-1)
        lower = np.quantile(samples, lower_q, axis=0)
        upper = np.quantile(samples, upper_q, axis=0)
        lower_flat = lower.reshape(n_assets, n_factors).reshape(-1)
        upper_flat = upper.reshape(n_assets, n_factors).reshape(-1)
        row = np.empty(lower_flat.size * 2, dtype=float)
        row[0::2] = lower_flat
        row[1::2] = upper_flat
        ci.iloc[pos] = row

    return ci


def cap_weights_by_beta_ci(
    weights: pd.Series,
    beta_ci: pd.DataFrame,
    tau_beta: float,
) -> pd.Series:
    """Scale weights when the maximum beta CI width breaches a threshold.

    Args:
      weights: Candidate instrument weights indexed by instrument identifier.
      beta_ci: Confidence interval panel from :func:`beta_ci_bootstrap`.
      tau_beta: Maximum acceptable CI width triggering weight shrinkage.

    Returns:
      Renormalised instrument weights with uncertain instruments scaled down.

    Raises:
      ValueError: If ``tau_beta`` is non-positive.
    """

    if tau_beta <= 0:
        raise ValueError("tau_beta must be positive")
    if weights.empty or beta_ci.empty:
        return weights.astype(float)
    valid = beta_ci.dropna(how="all")
    if valid.empty:
        return weights.astype(float)
    lower = valid.xs("lower", level="bound", axis=1)
    upper = valid.xs("upper", level="bound", axis=1)
    width = (upper - lower).abs()
    width_by_instrument = width.T.groupby(level="instrument").max().T
    width_per_instrument = width_by_instrument.max(axis=0)

    scaled = weights.astype(float).copy()
    for instrument, value in scaled.items():
        width_value = float(width_per_instrument.get(instrument, 0.0))
        if width_value > tau_beta and width_value > 0:
            coeff = max(tau_beta / width_value, 0.0)
            scaled.loc[instrument] = value * coeff

    total = float(scaled.sum())
    if total > 0:
        scaled = scaled / total
    return scaled
