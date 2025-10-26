"""Analytical helpers for reporting acceptance gates and attribution."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd

__all__ = ["acceptance_gates", "attribution_ic"]


def acceptance_gates(
    metrics: Mapping[str, np.ndarray | pd.Series | pd.Index],
    thresholds: Mapping[str, float],
    *,
    alpha_drawdown: float | None = None,
    alpha_cagr: float | None = None,
) -> dict[str, bool | float]:
    """Evaluate acceptance gates for drawdown exceedance and CAGR lower bound.

    Args:
      metrics: Mapping containing at least ``"max_drawdown"`` and ``"cagr"``
        entries with numerical samples from bootstrap simulations.
      thresholds: Mapping containing ``"max_drawdown_threshold"`` and
        ``"cagr_target"`` values specifying the gates.
      alpha_drawdown: Optional exceedance probability threshold. When ``None``
        defaults to ``thresholds.get("max_drawdown_exceedance", 0.05)``.
      alpha_cagr: Optional quantile level for the CAGR lower bound. When ``None``
        defaults to ``thresholds.get("cagr_alpha", 0.05)``.

    Returns:
      Dictionary containing the calculated exceedance probability,
      the CAGR lower bound and a ``passes`` flag summarising the gates.

    Raises:
      KeyError: If required keys are missing from ``metrics`` or ``thresholds``.
      ValueError: If no observations are available for the checks.
    """

    if "max_drawdown" not in metrics or "cagr" not in metrics:
        raise KeyError("metrics must expose 'max_drawdown' and 'cagr' samples")
    if "max_drawdown_threshold" not in thresholds or "cagr_target" not in thresholds:
        raise KeyError("thresholds must expose 'max_drawdown_threshold' and 'cagr_target'")

    drawdown_samples = np.asarray(metrics["max_drawdown"], dtype="float64")
    cagr_samples = np.asarray(metrics["cagr"], dtype="float64")
    if drawdown_samples.size == 0 or cagr_samples.size == 0:
        raise ValueError("metrics must contain samples for drawdown and CAGR")

    exceedance_level = alpha_drawdown
    if exceedance_level is None:
        exceedance_level = float(thresholds.get("max_drawdown_exceedance", 0.05))
    cagr_level = alpha_cagr
    if cagr_level is None:
        cagr_level = float(thresholds.get("cagr_alpha", 0.05))

    tol = float(thresholds["max_drawdown_threshold"])
    exceedance_probability = float(np.mean(drawdown_samples <= tol))
    cagr_lower_bound = float(np.quantile(cagr_samples, cagr_level, method="linear"))
    cagr_target = float(thresholds["cagr_target"])

    return {
        "max_drawdown_probability": exceedance_probability,
        "max_drawdown_gate": exceedance_probability <= exceedance_level,
        "cagr_lower_bound": cagr_lower_bound,
        "cagr_gate": cagr_lower_bound >= cagr_target,
        "passes": exceedance_probability <= exceedance_level and cagr_lower_bound >= cagr_target,
    }


def attribution_ic(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    *,
    window: int = 12,
) -> pd.DataFrame:
    """Compute instrument and factor attribution with rolling IC statistics.

    Args:
      weights: DataFrame of portfolio weights indexed by date.
      returns: DataFrame of instrument returns aligned with ``weights``.
      factors: DataFrame of factor returns aligned with the same index.
      window: Rolling window (in periods) used for the Information Coefficient.

    Returns:
      Multi-column DataFrame containing instrument contributions, factor
      contributions and rolling IC values.

    Raises:
      ValueError: If inputs do not share the same index or contain NaNs.
    """

    if not weights.index.equals(returns.index):
        raise ValueError("weights and returns must share the same index")
    if not weights.index.equals(factors.index):
        raise ValueError("factors must align with weights index")
    if weights.isna().any().any() or returns.isna().any().any() or factors.isna().any().any():
        raise ValueError("inputs must not contain missing values")

    instrument_contributions = weights.multiply(returns, fill_value=0.0)
    portfolio_returns = instrument_contributions.sum(axis=1)

    factor_betas: dict[str, pd.Series] = {}
    factor_ic: dict[str, pd.Series] = {}
    for column in factors.columns:
        series = factors[column]
        covariance = portfolio_returns.rolling(window=window, min_periods=window).cov(series)
        variance = series.rolling(window=window, min_periods=window).var()
        beta = covariance.div(variance.replace(0.0, np.nan))
        factor_betas[column] = beta.fillna(0.0)
        rolling_corr = portfolio_returns.rolling(window=window, min_periods=window).corr(series)
        factor_ic[column] = rolling_corr

    beta_frame = pd.DataFrame(factor_betas)
    factor_contributions = beta_frame.multiply(factors, fill_value=0.0)
    ic_frame = pd.DataFrame(factor_ic)

    return pd.concat(
        {
            "instrument_contribution": instrument_contributions,
            "factor_contribution": factor_contributions,
            "information_coefficient": ic_frame,
        },
        axis=1,
    )
