from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "OrthogonalizationResult",
    "condition_number",
    "merge_correlated_factors",
    "enforce_orthogonality",
]


@dataclass(slots=True)
class OrthogonalizationResult:
    factors: pd.DataFrame
    merged: dict[str, list[str]]
    loadings: pd.DataFrame
    condition_number: float


def condition_number(frame: pd.DataFrame) -> float:
    corr = np.corrcoef(frame.fillna(0.0).to_numpy().T)
    corr = np.nan_to_num(corr)
    return float(np.linalg.cond(corr))


def merge_correlated_factors(
    factors: pd.DataFrame,
    *,
    threshold: float,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    if not 0 < threshold < 1:
        raise ValueError("threshold must be between 0 and 1")

    working = factors.copy()
    mapping: dict[str, list[str]] = {name: [name] for name in working.columns}

    def _corr(df: pd.DataFrame) -> pd.DataFrame:
        corr = df.corr().abs().fillna(0.0)
        np.fill_diagonal(corr.values, 0.0)
        return corr

    corr = _corr(working)
    while working.shape[1] > 1 and corr.values.max() > threshold:
        idx = np.argwhere(corr.values == corr.values.max())[0]
        col_i = corr.index[idx[0]]
        col_j = corr.columns[idx[1]]
        combined = 0.5 * (working[col_i] + working[col_j])
        working[col_i] = combined
        mapping[col_i].extend(mapping.pop(col_j))
        working = working.drop(columns=col_j)
        corr = _corr(working)
    return working, mapping


def enforce_orthogonality(
    factors: pd.DataFrame,
    *,
    corr_threshold: float = 0.9,
    cond_threshold: float = 50.0,
) -> OrthogonalizationResult:
    if factors.empty:
        raise ValueError("No factors provided")

    merged_factors, mapping = merge_correlated_factors(factors, threshold=corr_threshold)

    clean = merged_factors.fillna(0.0)
    clean = clean.loc[:, clean.std(ddof=0) > 0]
    if clean.empty:
        raise ValueError("All factors became degenerate after merging")

    corr = np.corrcoef(clean.to_numpy().T)
    cond = float(np.linalg.cond(corr))
    if cond <= cond_threshold:
        loadings = pd.DataFrame(np.eye(clean.shape[1]), index=clean.columns, columns=clean.columns)
        return OrthogonalizationResult(clean, mapping, loadings, cond)

    centered = clean - clean.mean()
    cov = np.cov(centered.to_numpy().T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]

    transformed = centered.to_numpy() @ eigvecs
    transformed = transformed / np.maximum(np.std(transformed, axis=0, ddof=0), 1e-12)
    columns = [f"pc_{i + 1}" for i in range(transformed.shape[1])]
    orth = pd.DataFrame(transformed, index=clean.index, columns=columns)
    cond_new = float(np.linalg.cond(np.corrcoef(orth.to_numpy().T)))
    loadings = pd.DataFrame(eigvecs, index=clean.columns, columns=columns)

    return OrthogonalizationResult(orth, mapping, loadings, cond_new)
