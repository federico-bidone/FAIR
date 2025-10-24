"""Crisis probability committee combining market, volatility, and macro signals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm


@dataclass(frozen=True)
class CommitteeWeights:
    """Weights applied to each committee component."""

    hmm: float = 0.5
    volatility: float = 0.3
    macro: float = 0.2

    def normalised(self) -> tuple[float, float, float]:
        total = float(self.hmm + self.volatility + self.macro)
        if total <= 0:
            msg = "Committee weights must sum to a positive value."
            raise ValueError(msg)
        return (self.hmm / total, self.volatility / total, self.macro / total)


def _filter_hmm_prob(ret: pd.Series) -> pd.Series:
    """Infer crisis-state probabilities via a fixed two-state Gaussian HMM."""

    if ret.empty:
        return pd.Series(dtype=float)

    ret = ret.sort_index().astype(float).fillna(0.0)
    # Transition/emission parameters chosen for persistence and heavy-crisis tails.
    transition = np.array([[0.97, 0.03], [0.15, 0.85]], dtype=float)
    mu = np.array([0.0005, -0.0025], dtype=float)
    sigma = np.array([0.010, 0.025], dtype=float)

    state_prob = np.array([0.95, 0.05], dtype=float)
    crisis_probs = np.empty(len(ret), dtype=float)

    for idx, value in enumerate(ret.to_numpy()):
        emission = norm.pdf(value, loc=mu, scale=sigma) + 1e-16
        predicted = transition.T @ state_prob
        posterior = emission * predicted
        posterior_sum = posterior.sum()
        if posterior_sum <= 0:
            posterior = state_prob
            posterior_sum = posterior.sum()
        state_prob = posterior / posterior_sum
        crisis_probs[idx] = state_prob[1]

    return pd.Series(crisis_probs, index=ret.index).clip(0.0, 1.0)


def _volatility_stress(vol: pd.Series) -> pd.Series:
    if vol.empty:
        return pd.Series(dtype=float)
    vol = vol.sort_index().astype(float).replace([np.inf, -np.inf], np.nan).ffill()
    median = vol.rolling(window=63, min_periods=10).median()
    ratio = (vol / median).replace([np.inf, -np.inf], np.nan).fillna(1.0)
    scaled = np.tanh(2.5 * (ratio - 1.0))  # emphasise >1.0 deviations while bounding output
    return pd.Series(0.5 * (scaled + 1.0), index=vol.index).clip(0.0, 1.0)


def _macro_slowdown(macro: pd.DataFrame) -> pd.Series:
    if macro.empty:
        return pd.Series(dtype=float)

    macro = macro.sort_index().astype(float)
    macro = macro.replace([np.inf, -np.inf], np.nan).ffill().dropna(how="all")
    if macro.empty:
        return pd.Series(dtype=float)

    diff = macro - macro.rolling(window=3, min_periods=2).mean()
    std = macro.rolling(window=6, min_periods=3).std().replace(0.0, np.nan)
    zscore = diff.divide(std).clip(-5.0, 5.0).fillna(0.0)
    slowdown = 0.5 * (1.0 - np.tanh(zscore / 3.0))
    slowdown = slowdown.mean(axis=1)
    return slowdown.reindex(macro.index).fillna(0.5).clip(0.0, 1.0)


def crisis_probability(
    returns: pd.DataFrame,
    vol: pd.Series,
    macro: pd.DataFrame,
    weights: CommitteeWeights | None = None,
) -> pd.Series:
    """Estimate crisis probabilities from committee signals.

    Parameters
    ----------
    returns
        Point-in-time return panel (columns = instruments). Rows should align on
        timestamps and are averaged equally to infer the latent market regime.
    vol
        Volatility proxy indexed by the same timestamps (e.g. annualised realised
        volatility). Higher values imply elevated risk.
    macro
        Macro indicators indexed by timestamp (e.g. PMI, unemployment, inflation).
        Slowdowns should push probabilities higher after standardisation.
    weights
        Optional component weights. When omitted the default mix is 50% HMM,
        30% volatility, 20% macro.

    Returns
    -------
    pandas.Series
        Crisis probability in [0, 1] for each timestamp in the intersection of
        the provided inputs.
    """

    weights = weights or CommitteeWeights()
    w_hmm, w_vol, w_macro = weights.normalised()

    aligned_index = returns.index
    if not vol.empty:
        aligned_index = aligned_index.intersection(vol.index)
    if not macro.empty:
        aligned_index = aligned_index.intersection(macro.index)

    if aligned_index.empty:
        return pd.Series(dtype=float)

    ret_avg = returns.sort_index().reindex(aligned_index).mean(axis=1)
    hmm_prob = _filter_hmm_prob(ret_avg)
    vol_prob = _volatility_stress(vol.reindex(aligned_index))
    macro_prob = _macro_slowdown(macro.reindex(aligned_index))

    # Align outputs and fill missing components with neutral priors.
    hmm_prob = hmm_prob.reindex(aligned_index).fillna(0.05)
    vol_prob = vol_prob.reindex(aligned_index).fillna(0.5)
    macro_prob = macro_prob.reindex(aligned_index).fillna(0.5)

    combined = w_hmm * hmm_prob + w_vol * vol_prob + w_macro * macro_prob
    return combined.clip(0.0, 1.0)


__all__ = [
    "CommitteeWeights",
    "crisis_probability",
]
