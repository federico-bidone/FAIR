from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "HampelConfig",
    "apply_hampel",
    "winsorize_series",
    "clean_price_history",
    "prepare_estimation_copy",
]


@dataclass(slots=True)
class HampelConfig:
    window: int = 7
    n_sigma: float = 3.0

    def __post_init__(self) -> None:
        if self.window <= 0:
            raise ValueError("window must be positive")
        if self.n_sigma <= 0:
            raise ValueError("n_sigma must be positive")


def apply_hampel(series: pd.Series, config: HampelConfig | None = None) -> pd.Series:
    """Apply a Hampel filter using median and MAD to suppress spikes."""

    config = config or HampelConfig()
    if series.empty:
        return series
    window = config.window
    median = series.rolling(window=window, center=True, min_periods=1).median()
    diff = (series - median).abs()
    mad = diff.rolling(window=window, center=True, min_periods=1).median()
    mad = mad.replace(0, np.nan)
    threshold = config.n_sigma * 1.4826 * mad
    threshold = threshold.fillna(0.0)
    mask = diff > threshold
    cleaned = series.copy()
    cleaned[mask] = median[mask]
    return cleaned


def winsorize_series(
    series: pd.Series,
    *,
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.Series:
    """Clip the series to the given quantile bounds."""

    if not 0.0 <= lower < upper <= 1.0:
        raise ValueError("invalid quantile bounds")
    if series.empty:
        return series
    lower_q, upper_q = series.quantile([lower, upper])
    return series.clip(lower=lower_q, upper=upper_q)


def clean_price_history(
    frame: pd.DataFrame,
    *,
    value_column: str = "price",
    group_column: str = "symbol",
    hampel: HampelConfig | None = None,
) -> pd.DataFrame:
    """Apply Hampel cleaning per symbol."""

    if frame.empty:
        return frame
    if value_column not in frame.columns:
        raise ValueError(f"expected column {value_column}")

    work = frame.copy()
    work[value_column] = work.groupby(group_column, group_keys=False)[value_column].apply(
        lambda s: apply_hampel(s, hampel)
    )
    return work


def prepare_estimation_copy(
    returns: pd.Series,
    *,
    winsor_quantiles: tuple[float, float] = (0.01, 0.99),
) -> pd.Series:
    """Return winsorised copy of the return series for estimation-only paths."""

    lower, upper = winsor_quantiles
    return winsorize_series(returns, lower=lower, upper=upper)
