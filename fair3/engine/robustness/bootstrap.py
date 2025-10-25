from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fair3.engine.utils.rand import generator_from_seed

__all__ = [
    "RobustnessGates",
    "block_bootstrap_metrics",
]


@dataclass(frozen=True)
class RobustnessGates:
    """Statistiche di accettazione calcolate dal laboratorio di robustezza."""

    max_drawdown_threshold: float
    cagr_target: float
    exceedance_probability: float
    cagr_lower_bound: float
    alpha: float

    def passes(self) -> bool:
        """Restituisce ``True`` se drawdown e CAGR rispettano le soglie."""

        level = 1.0 - self.alpha
        return self.exceedance_probability <= level and self.cagr_lower_bound >= self.cagr_target


def _prepare_returns(returns: Iterable[float]) -> pd.Series:
    """Converte gli input in Serie Pandas e valida che non siano vuoti."""

    series = pd.Series(pd.Series(returns).astype("float64"), copy=False)
    if series.empty:
        raise ValueError("returns deve contenere almeno un'osservazione")
    return series.dropna()


def _block_bootstrap_samples(
    arr: np.ndarray,
    *,
    block_size: int,
    draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Genera campioni bootstrap concatenando blocchi estratti con rimpiazzo."""

    n_obs = arr.shape[0]
    if block_size < 1:
        raise ValueError("block_size deve essere >= 1")
    if block_size > n_obs:
        raise ValueError("block_size non può superare la lunghezza dei rendimenti")
    reps = int(np.ceil(n_obs / block_size))
    max_start = max(1, n_obs - block_size + 1)
    samples = np.empty((draws, n_obs), dtype="float64")
    for draw in range(draws):
        # Selezioniamo gli indici iniziali dei blocchi e poi li concateniamo.
        indices = rng.integers(0, max_start, size=reps)
        path = np.concatenate([arr[idx : idx + block_size] for idx in indices])
        samples[draw] = path[:n_obs]
    return samples


def _max_drawdown(path: np.ndarray) -> float:
    """Calcola il drawdown massimo cumulato lungo il percorso fornito."""

    wealth = np.cumprod(1.0 + path)
    if np.any(wealth <= 0):
        # Perdita catastrofica: consideriamo un drawdown del -100%.
        return -1.0
    peaks = np.maximum.accumulate(wealth)
    drawdowns = wealth / peaks - 1.0
    return float(np.min(drawdowns))


def _cagr(path: np.ndarray, *, periods_per_year: int) -> float:
    """Deriva il CAGR annualizzato del percorso di rendimenti."""

    total_return = float(np.prod(1.0 + path))
    n_obs = path.shape[0]
    if n_obs == 0:
        return 0.0
    if total_return <= 0:
        return -1.0
    years = n_obs / periods_per_year
    if years <= 0:
        return 0.0
    return float(total_return ** (1.0 / years) - 1.0)


def block_bootstrap_metrics(
    returns: Iterable[float],
    *,
    block_size: int = 60,
    draws: int = 1_000,
    periods_per_year: int = 252,
    alpha: float = 0.95,
    max_drawdown_threshold: float = -0.25,
    cagr_target: float = 0.03,
    seed: int | np.random.Generator | None = None,
) -> tuple[pd.DataFrame, RobustnessGates]:
    """Esegue un bootstrap a blocchi sui rendimenti e calcola le soglie finali."""

    series = _prepare_returns(returns)
    rng = generator_from_seed(seed, stream="robustness")
    samples = _block_bootstrap_samples(
        series.to_numpy(copy=False), block_size=block_size, draws=draws, rng=rng
    )

    max_drawdowns = np.apply_along_axis(_max_drawdown, 1, samples)
    cagrs = np.apply_along_axis(_cagr, 1, samples, periods_per_year=periods_per_year)

    metrics = pd.DataFrame(
        {
            "draw": np.arange(draws, dtype=int),
            "max_drawdown": max_drawdowns,
            "cagr": cagrs,
        }
    )

    severe = (max_drawdowns <= max_drawdown_threshold).mean()
    lower_bound = float(np.quantile(cagrs, 1.0 - alpha, method="linear"))
    gates = RobustnessGates(
        max_drawdown_threshold=max_drawdown_threshold,
        cagr_target=cagr_target,
        exceedance_probability=float(severe),
        cagr_lower_bound=lower_bound,
        alpha=alpha,
    )
    return metrics, gates
