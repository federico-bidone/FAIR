from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from fair3.engine.utils.rand import generator_from_seed

_STREAM_BOOT = "mapping.beta_bootstrap"


def _prepare_frames(
    returns: pd.DataFrame, factors: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Index]:
    common = returns.index.intersection(factors.index)
    if common.empty:
        raise ValueError("returns and factors must share a non-empty index")
    ret = returns.loc[common].sort_index()
    fac = factors.loc[common].sort_index()
    combined = ret.join(fac, how="inner")
    combined = combined.dropna(how="any")
    if combined.empty:
        raise ValueError("returns and factors alignment produced no rows")
    ret_aligned = combined[returns.columns]
    fac_aligned = combined[factors.columns]
    return ret_aligned, fac_aligned, combined.index


def _enforce_signs(values: np.ndarray, factors: Iterable[str], sign: dict[str, int]) -> None:
    if not sign:
        return
    for j, factor in enumerate(factors):
        desired = sign.get(factor)
        if desired == 1:
            values[j, :] = np.maximum(values[j, :], 0.0)
        elif desired == -1:
            values[j, :] = np.minimum(values[j, :], 0.0)


def _solve_ridge(xtx: np.ndarray, xty: np.ndarray) -> np.ndarray:
    try:
        return np.linalg.solve(xtx, xty)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(xtx) @ xty


def rolling_beta_ridge(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    window: int,
    lambda_beta: float,
    sign: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Estimate rolling ridge betas with optional sign governance."""

    if window <= 1:
        raise ValueError("window must be greater than one")
    if lambda_beta < 0:
        raise ValueError("lambda_beta must be non-negative")
    sign_dict = dict(sign or {})
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
        _enforce_signs(beta_window, fac.columns, sign_dict)
        row_values = beta_window.T.reshape(-1)
        betas.iloc[pos] = row_values

    betas.attrs["window"] = window
    betas.attrs["ridge_lambda"] = float(lambda_beta)
    if sign_dict:
        betas.attrs["sign_constraints"] = sign_dict
    return betas


def beta_ci_bootstrap(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    beta_ts: pd.DataFrame,
    B: int = 1000,  # noqa: N803
    alpha: float = 0.2,
) -> pd.DataFrame:
    """Bootstrap confidence intervals for rolling betas."""

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
            _enforce_signs(beta_sample, fac.columns, sign_dict)
            samples[b] = beta_sample.T.reshape(-1)
        lower = np.quantile(samples, lower_q, axis=0)
        upper = np.quantile(samples, upper_q, axis=0)
        # Build interleaved lower/upper values
        lower_flat = lower.reshape(n_assets, n_factors).reshape(-1)
        upper_flat = upper.reshape(n_assets, n_factors).reshape(-1)
        row = np.empty(lower_flat.size * 2, dtype=float)
        row[0::2] = lower_flat
        row[1::2] = upper_flat
        ci.iloc[pos] = row

    return ci
