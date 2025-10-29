from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fair3.engine.utils.rand import generator_from_seed

__all__ = [
    "FactorValidationResult",
    "cross_purged_splits",
    "deflated_sharpe_ratio",
    "white_reality_check_pvalue",
    "fdr_bh",
    "validate_factor_set",
]


@dataclass(slots=True)
class FactorValidationResult:
    name: str
    sharpe: float
    dsr: float
    p_value: float
    ic_mean: float
    ic_std: float
    passed_fdr: bool


def cross_purged_splits(
    dates: pd.DatetimeIndex,
    *,
    n_splits: int,
    embargo: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Restituisce split deterministici cross-purged con embargo sul calendario."""

    if n_splits < 2:
        raise ValueError("n_splits must be >= 2")
    embargo = max(0, int(embargo))
    unique_dates = np.array(sorted(pd.Index(dates).unique()))
    if len(unique_dates) < n_splits:
        raise ValueError("Not enough observations for the requested splits")

    fold_sizes = np.full(n_splits, len(unique_dates) // n_splits)
    fold_sizes[: len(unique_dates) % n_splits] += 1

    splits: list[tuple[np.ndarray, np.ndarray]] = []
    start = 0
    for fold_size in fold_sizes:
        stop = start + fold_size
        test = unique_dates[start:stop]
        embargo_start = max(0, start - embargo)
        embargo_stop = min(len(unique_dates), stop + embargo)
        train_mask = np.ones(len(unique_dates), dtype=bool)
        train_mask[embargo_start:embargo_stop] = False
        train = unique_dates[train_mask]
        splits.append((train, test))
        start = stop
    return splits


def _sharpe(series: pd.Series) -> float:
    clean = series.dropna()
    if clean.empty:
        return 0.0
    mean = clean.mean()
    std = clean.std(ddof=1)
    if std == 0:
        return 0.0
    return float(mean / std * math.sqrt(252))


def deflated_sharpe_ratio(series: pd.Series) -> float:
    """Compute a simplified deflated Sharpe ratio following Lopez de Prado."""

    clean = series.dropna()
    n = len(clean)
    if n < 5:
        return 0.0
    sr = _sharpe(clean)
    skew = float(clean.skew())
    kurt = float(clean.kurt())
    numerator = sr - (skew * sr + 0.5 * (kurt - 3) * sr**2) / max(n, 1)
    denominator = math.sqrt(max((1 - skew * sr + 0.5 * (kurt - 3) * sr**2) / max(n, 1), 1e-12))
    z = numerator / denominator
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def white_reality_check_pvalue(
    series: pd.Series,
    *,
    bootstrap_samples: int = 200,
    seed: int | None = None,
) -> float:
    """Approximate a White Reality Check style p-value via permutation bootstrap."""

    clean = series.dropna()
    if len(clean) < 5:
        return 1.0
    observed = _sharpe(clean)
    rng = generator_from_seed(seed, stream="factor_validation")
    arr = clean.to_numpy()
    exceed = 0
    for _ in range(int(bootstrap_samples)):
        perm = rng.permutation(arr)
        boot = _sharpe(pd.Series(perm, index=clean.index))
        if boot >= observed:
            exceed += 1
    return (exceed + 1) / (bootstrap_samples + 1)


def fdr_bh(p_values: pd.Series | list[float], alpha: float = 0.1) -> np.ndarray:
    values = np.array(pd.Series(p_values).to_numpy(), dtype=float)
    n = values.size
    if n == 0:
        return np.array([], dtype=bool)
    order = np.argsort(values)
    ranked = values[order]
    thresholds = alpha * (np.arange(1, n + 1) / n)
    below = ranked <= thresholds
    if not np.any(below):
        return np.zeros(n, dtype=bool)
    max_idx = np.max(np.where(below))
    mask = np.zeros(n, dtype=bool)
    mask[: max_idx + 1] = True
    result = np.zeros(n, dtype=bool)
    result[order] = mask
    return result


def validate_factor_set(
    factors: pd.DataFrame,
    asset_returns: pd.DataFrame,
    *,
    n_splits: int = 5,
    embargo: int = 5,
    alpha: float = 0.1,
    seed: int | None = None,
) -> list[FactorValidationResult]:
    """Validate factor efficacy with CP-CV, DSR, White RC, and FDR filtering."""

    if not isinstance(factors.index, pd.DatetimeIndex):
        raise TypeError("factors index must be DatetimeIndex")

    pivot = _prepare_asset_returns(asset_returns, factors.index)
    target = pivot.mean(axis=1).fillna(0.0)

    splits = cross_purged_splits(target.index, n_splits=n_splits, embargo=embargo)

    ic_matrix: dict[str, list[float]] = {name: [] for name in factors.columns}
    for _train, test in splits:
        test_idx = target.index.intersection(test)
        if test_idx.empty:
            continue
        target_slice = target.loc[test_idx]
        for name, series in factors.items():
            factor_slice = series.reindex(test_idx)
            if factor_slice.std(ddof=0) == 0:
                ic_matrix[name].append(0.0)
                continue
            corr = np.corrcoef(factor_slice.to_numpy(), target_slice.to_numpy())
            ic = float(corr[0, 1]) if corr.size == 4 else 0.0
            ic_matrix[name].append(np.nan_to_num(ic))

    p_values: list[float] = []
    results: list[FactorValidationResult] = []
    rng_seed = seed if seed is not None else 0

    for name, series in factors.items():
        sharpe = _sharpe(series)
        dsr = deflated_sharpe_ratio(series)
        p_val = white_reality_check_pvalue(series, seed=rng_seed)
        ic_scores = ic_matrix.get(name, [])
        ic_mean = float(np.nanmean(ic_scores)) if ic_scores else 0.0
        ic_std = float(np.nanstd(ic_scores)) if ic_scores else 0.0
        p_values.append(p_val)
        results.append(
            FactorValidationResult(
                name=name,
                sharpe=sharpe,
                dsr=dsr,
                p_value=p_val,
                ic_mean=ic_mean,
                ic_std=ic_std,
                passed_fdr=False,
            )
        )

    mask = fdr_bh(p_values, alpha=alpha)
    for idx, passed in enumerate(mask):
        results[idx].passed_fdr = bool(passed)

    return results


def _prepare_asset_returns(asset_returns: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    if isinstance(asset_returns.index, pd.MultiIndex):
        if "ret" in asset_returns.columns:
            pivot = asset_returns["ret"].unstack(level=1)
        else:
            pivot = asset_returns.unstack(level=1)
    else:
        pivot = asset_returns.copy()
    pivot = pivot.sort_index()
    pivot = pivot.reindex(index, method="ffill").fillna(0.0)
    return pivot
