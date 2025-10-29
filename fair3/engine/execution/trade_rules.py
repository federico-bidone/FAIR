"""Execution decision helper rules."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fair3.engine.robustness.bootstrap import block_bootstrap, eb_lower_bound


def drift_bands_exceeded(
    w_old: np.ndarray,
    w_new: np.ndarray,
    rc_old: np.ndarray,
    rc_new: np.ndarray,
    band: float,
) -> bool:
    """Restituisce ``True`` se il drift di peso o di contributo di rischio supera ``band``."""

    w_old = np.asarray(w_old, dtype=float)
    w_new = np.asarray(w_new, dtype=float)
    rc_old = np.asarray(rc_old, dtype=float)
    rc_new = np.asarray(rc_new, dtype=float)

    shapes = {w_old.shape, w_new.shape, rc_old.shape, rc_new.shape}
    if len(shapes) != 1:
        raise ValueError("Input arrays must share the same shape")
    if band < 0:
        raise ValueError("band must be non-negative")

    weight_drift = float(np.max(np.abs(w_new - w_old)))
    rc_drift = float(np.max(np.abs(rc_new - rc_old)))
    return (weight_drift > band) or (rc_drift > band)


def expected_benefit(
    delta_w: np.ndarray,
    mu_instr: np.ndarray,
    sigma_instr: np.ndarray,
    w_old: np.ndarray,
    w_new: np.ndarray,
) -> float:
    """Calcola un expected benefit minimo per l'operatività proposta."""

    delta_w = np.asarray(delta_w, dtype=float)
    mu_instr = np.asarray(mu_instr, dtype=float)
    sigma_instr = np.asarray(sigma_instr, dtype=float)
    w_old = np.asarray(w_old, dtype=float)
    w_new = np.asarray(w_new, dtype=float)

    if mu_instr.ndim != 1 or w_old.ndim != 1 or w_new.ndim != 1 or delta_w.ndim != 1:
        raise ValueError("All vector inputs must be one-dimensional")
    if mu_instr.shape != w_old.shape or w_old.shape != w_new.shape or delta_w.shape != w_old.shape:
        raise ValueError("All vector inputs must share the same shape")
    if sigma_instr.shape != (w_old.size, w_old.size):
        raise ValueError("sigma_instr must be square with dimension matching weights")

    if not np.allclose(delta_w, w_new - w_old):
        raise ValueError("delta_w must equal w_new - w_old")

    mu_old = float(w_old @ mu_instr)
    mu_new = float(w_new @ mu_instr)
    var_old = float(w_old @ sigma_instr @ w_old)
    var_new = float(w_new @ sigma_instr @ w_new)
    variance_change = var_new - var_old

    return (mu_new - mu_old) - 0.5 * variance_change


def expected_benefit_distribution(
    returns: pd.DataFrame,
    delta_w: np.ndarray,
    w_old: np.ndarray,
    w_new: np.ndarray,
    *,
    block_size: int = 60,
    n_resamples: int = 1_000,
    seed: int | np.random.Generator | None = None,
) -> pd.DataFrame:
    """Costruisce la distribuzione bootstrap dell'Expected Benefit.

    Args:
      returns: DataFrame di rendimenti strumentali ordinati temporalmente.
      delta_w: Variazione di peso proposta per ciascun strumento.
      w_old: Vettore di pesi correnti.
      w_new: Vettore di pesi proposti.
      block_size: Ampiezza dei blocchi bootstrap.
      n_resamples: Numero di resample da generare.
      seed: Seed o generatore deterministico da impiegare.

    Returns:
      DataFrame indicizzato per ``draw`` con la colonna ``expected_benefit``.

    Raises:
      ValueError: Se le dimensioni non sono coerenti o i dati contengono NaN.
    """

    if returns.empty:
        raise ValueError("returns must contain at least one observation")

    frame = returns.astype("float64", copy=False)
    if frame.isna().any().any():
        raise ValueError("returns must not contain missing values")

    n_assets = frame.shape[1]
    delta_w = np.asarray(delta_w, dtype=float)
    w_old = np.asarray(w_old, dtype=float)
    w_new = np.asarray(w_new, dtype=float)

    if n_assets != delta_w.size:
        raise ValueError("returns columns must match delta_w size")
    if w_old.shape != w_new.shape or w_old.shape[0] != n_assets:
        raise ValueError("weight vectors must align with returns columns")

    samples = block_bootstrap(
        frame,
        block_size=block_size,
        n_resamples=n_resamples,
        seed=seed,
    )

    eb_values: list[float] = []
    for sample in samples:
        mu_sample = sample.mean(axis=0)
        sigma_sample = sample.cov()
        sigma_array = np.nan_to_num(sigma_sample.to_numpy(), nan=0.0)
        eb = expected_benefit(delta_w, mu_sample.to_numpy(), sigma_array, w_old, w_new)
        eb_values.append(float(eb))

    draws = pd.Index(range(len(eb_values)), name="draw", dtype=int)
    return pd.DataFrame({"expected_benefit": eb_values}, index=draws)


def expected_benefit_lower_bound(
    returns: pd.DataFrame,
    delta_w: np.ndarray,
    w_old: np.ndarray,
    w_new: np.ndarray,
    *,
    alpha: float,
    block_size: int = 60,
    n_resamples: int = 1_000,
    seed: int | np.random.Generator | None = None,
) -> float:
    """Calcola EB_LB dalla distribuzione bootstrap.

    Args:
      returns: DataFrame di rendimenti strumentali.
      delta_w: Variazione di peso proposta.
      w_old: Vettore di pesi correnti.
      w_new: Vettore di pesi proposti.
      alpha: Quantile da estrarre dalla distribuzione.
      block_size: Ampiezza dei blocchi bootstrap.
      n_resamples: Numero di resample da generare.
      seed: Seed o generatore deterministico da impiegare.

    Returns:
      L'Expected Benefit Lower Bound calcolato al quantile ``alpha``.
    """

    distribution = expected_benefit_distribution(
        returns,
        delta_w,
        w_old,
        w_new,
        block_size=block_size,
        n_resamples=n_resamples,
        seed=seed,
    )
    return eb_lower_bound(distribution, alpha=alpha)
