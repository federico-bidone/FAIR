"""Bootstrap utilities for robustness analysis in FAIR-III."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fair3.engine.utils.rand import generator_from_seed

__all__ = [
    "RobustnessGates",
    "block_bootstrap",
    "block_bootstrap_metrics",
    "eb_lower_bound",
]


def block_bootstrap(
    panel: pd.DataFrame,
    *,
    block_size: int,
    n_resamples: int,
    seed: int | np.random.Generator | None = None,
) -> list[pd.DataFrame]:
    """Genera resample bootstrap a blocchi preservando la correlazione.

    Args:
      panel: DataFrame con osservazioni ordinate temporalmente e colonne
        numeriche omogenee.
      block_size: Numero di osservazioni consecutive che compongono ciascun
        blocco.
      n_resamples: Numero di resample da produrre.
      seed: Seed deterministico o generatore NumPy da utilizzare; se ``None``
        viene adottato lo stream ``robustness_bootstrap``.

    Returns:
      Lista di DataFrame con stessa forma, indice e colonne di ``panel``.

    Raises:
      ValueError: Se il pannello è vuoto, contiene valori mancanti o se i
        parametri ``block_size``/``n_resamples`` non sono positivi.
    """

    if panel.empty:
        raise ValueError("panel must contain at least one observation")
    if block_size < 1:
        raise ValueError("block_size must be >= 1")
    if n_resamples < 1:
        raise ValueError("n_resamples must be >= 1")
    if block_size > len(panel.index):
        raise ValueError("block_size cannot exceed number of observations")
    if panel.isna().any().any():
        raise ValueError("panel must not contain missing values for bootstrap")

    frame = panel.astype("float64", copy=False)
    values = frame.to_numpy(copy=False)
    rng = generator_from_seed(seed, stream="robustness_bootstrap")

    n_obs = values.shape[0]
    reps = int(np.ceil(n_obs / block_size))
    max_start = max(1, n_obs - block_size + 1)
    samples: list[pd.DataFrame] = []

    for _ in range(n_resamples):
        starts = rng.integers(0, max_start, size=reps)
        resampled = np.concatenate([values[start : start + block_size] for start in starts])
        sliced = resampled[:n_obs]
        sample = pd.DataFrame(sliced, index=frame.index, columns=frame.columns)
        samples.append(sample)

    return samples


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


def _sharpe(path: np.ndarray, *, periods_per_year: int) -> float:
    """Calcola lo Sharpe annualizzato del percorso fornito.

    Args:
      path: Array di rendimenti campionati.
      periods_per_year: Numero di periodi per anno utilizzato per annualizzare.

    Returns:
      Valore dello Sharpe ratio annualizzato.
    """

    std = float(np.std(path, ddof=0))
    if std == 0:
        return 0.0
    mean = float(np.mean(path))
    return float(mean / std * np.sqrt(periods_per_year))


def _cvar_alpha(path: np.ndarray, *, alpha: float) -> float:
    """Restituisce la CVaR ``alpha`` dei rendimenti forniti.

    Args:
      path: Array di rendimenti del campione.
      alpha: Livello di confidenza (es. 0.95).

    Returns:
      Valore medio dei rendimenti nella coda sinistra.
    """

    if path.size == 0:
        return 0.0
    cutoff = max(1, int(np.ceil((1 - alpha) * path.size)))
    tail = np.sort(path)[:cutoff]
    return float(np.mean(tail))


def _edar_alpha(path: np.ndarray, *, window: int, alpha: float) -> float:
    """Calcola l'Expected Drawdown-at-Risk su finestra mobile.

    Args:
      path: Array di rendimenti del campione.
      window: Numero di periodi considerati per ciascuna finestra.
      alpha: Livello di confidenza utilizzato per l'estrazione della coda.

    Returns:
      Expected Drawdown-at-Risk calcolato sulla finestra mobile.
    """

    n_obs = path.size
    if n_obs == 0:
        return 0.0
    win = min(window, n_obs)
    if win <= 0:
        return 0.0
    horizons: list[float] = []
    for end in range(win, n_obs + 1):
        window_slice = path[end - win : end]
        total = float(np.prod(1.0 + window_slice) - 1.0)
        horizons.append(total)
    values = np.sort(np.array(horizons, dtype="float64"))
    cutoff = max(1, int(np.ceil((1 - alpha) * values.size)))
    tail = np.minimum(values[:cutoff], 0.0)
    return float(np.mean(tail))


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
    sharpes = np.apply_along_axis(_sharpe, 1, samples, periods_per_year=periods_per_year)
    cvars = np.apply_along_axis(_cvar_alpha, 1, samples, alpha=alpha)
    edar_window = int(periods_per_year * 3)
    edars = np.apply_along_axis(_edar_alpha, 1, samples, window=edar_window, alpha=alpha)

    metrics = pd.DataFrame(
        {
            "draw": np.arange(draws, dtype=int),
            "max_drawdown": max_drawdowns,
            "cagr": cagrs,
            "sharpe": sharpes,
            "cvar": cvars,
            "edar": edars,
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


def eb_lower_bound(expected_benefits: pd.DataFrame, *, alpha: float) -> float:
    """Restituisce il quantile ``alpha`` della distribuzione di EB.

    Args:
      expected_benefits: DataFrame con una colonna ``expected_benefit`` che
        raccoglie gli esiti bootstrap.
      alpha: Quantile da estrarre (tipicamente 0.01–0.10 per bound
        conservativi).

    Returns:
      Il quantile ``alpha`` della distribuzione.

    Raises:
      ValueError: Se ``alpha`` non appartiene all'intervallo ``(0, 1)``, la
        colonna è assente oppure priva di osservazioni valide.
    """

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must fall in the open interval (0, 1)")
    if "expected_benefit" not in expected_benefits.columns:
        raise ValueError("expected_benefits must expose an 'expected_benefit' column")

    series = expected_benefits["expected_benefit"].dropna()
    if series.empty:
        raise ValueError("expected_benefit column must contain at least one observation")

    return float(series.quantile(alpha, interpolation="linear"))
