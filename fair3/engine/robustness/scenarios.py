"""Scenari di shock storici per il laboratorio di robustezza.

Qui vengono definite le traiettorie stilizzate utilizzate negli stress test
su FAIR-III insieme agli helper per rigiocarle contro serie storiche. I
commenti spiegano in italiano come vengono calcolate le metriche e come
vengono scalati gli scenari rispetto alla volatilità di base.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "ShockScenario",
    "DEFAULT_SHOCKS",
    "default_shock_scenarios",
    "replay_shocks",
]


@dataclass(frozen=True)
class ShockScenario:
    """Rappresenta un percorso di rendimenti stilizzato per gli stress test."""

    name: str
    returns: np.ndarray


def _scenario_max_drawdown(path: np.ndarray) -> float:
    """Calcola il drawdown massimo cumulato di uno scenario."""

    wealth = np.cumprod(1.0 + path)
    if np.any(wealth <= 0):
        return -1.0
    peaks = np.maximum.accumulate(wealth)
    drawdowns = wealth / peaks - 1.0
    return float(np.min(drawdowns))


def _scenario_cagr(path: np.ndarray, *, periods_per_year: int) -> float:
    """Deriva il CAGR annualizzato del percorso fornito."""

    total_return = float(np.prod(1.0 + path))
    n_obs = path.shape[0]
    if n_obs == 0 or total_return <= 0:
        return -1.0
    years = n_obs / periods_per_year
    if years <= 0:
        return -1.0
    return float(total_return ** (1.0 / years) - 1.0)


# Collezione predefinita di shock storici che copre crisi energetiche,
# finanziarie e pandemiche utilizzate nel QA del sistema.
DEFAULT_SHOCKS: tuple[ShockScenario, ...] = (
    ShockScenario(
        name="1973_oil_crisis",
        returns=np.array(
            [
                -0.045,
                -0.035,
                -0.028,
                -0.020,
                -0.010,
                0.005,
                -0.012,
                -0.008,
                0.004,
                0.006,
                0.005,
                -0.007,
            ],
            dtype="float64",
        ),
    ),
    ShockScenario(
        name="2008_gfc",
        returns=np.array(
            [
                -0.120,
                -0.085,
                -0.160,
                -0.090,
                -0.040,
                0.020,
                0.030,
                -0.015,
                -0.025,
                0.018,
                0.022,
                0.015,
            ],
            dtype="float64",
        ),
    ),
    ShockScenario(
        name="2020_covid",
        returns=np.array(
            [
                -0.135,
                -0.110,
                0.065,
                0.045,
                0.030,
                -0.020,
                0.015,
                0.012,
                0.018,
                -0.005,
                0.008,
                0.010,
            ],
            dtype="float64",
        ),
    ),
    ShockScenario(
        name="1970s_stagflation",
        returns=np.array(
            [
                -0.025,
                -0.022,
                -0.018,
                -0.012,
                -0.010,
                -0.008,
                -0.006,
                -0.004,
                -0.003,
                -0.002,
                -0.001,
                0.000,
            ],
            dtype="float64",
        ),
    ),
)


def default_shock_scenarios() -> tuple[ShockScenario, ...]:
    """Restituisce gli shock storici forniti di default.

    Returns:
        Tupla immutabile con gli scenari di shock da utilizzare per gli stress
        test quando l'utente non fornisce una lista personalizzata.
    """

    return DEFAULT_SHOCKS


def _scale_scenario(returns: np.ndarray, target_vol: float) -> np.ndarray:
    """Scala lo scenario per pareggiare la volatilità dei rendimenti base."""

    scenario_vol = float(np.std(returns, ddof=0))
    if scenario_vol == 0 or target_vol == 0:
        return np.zeros_like(returns)
    scale = target_vol / scenario_vol
    return returns * scale


def replay_shocks(
    base_returns: Iterable[float],
    *,
    scenarios: Sequence[ShockScenario] | None = None,
    scale_to_base_vol: bool = True,
    periods_per_year: int = 252,
) -> pd.DataFrame:
    """Rigioca gli shock storici sui rendimenti osservati e riporta le metriche.

    Args:
        base_returns: Rendimento della strategia su cui effettuare lo stress
            test.
        scenarios: Elenco di scenari da applicare; ``None`` usa
            :data:`DEFAULT_SHOCKS`.
        scale_to_base_vol: Se ``True`` scala gli scenari per eguagliare la
            volatilità della serie base.
        periods_per_year: Numero di periodi utilizzati per annualizzare il CAGR.

    Returns:
        DataFrame ordinato per drawdown contenente le metriche principali per
        ciascuno scenario.
    """

    base_series = pd.Series(base_returns, dtype="float64")
    if base_series.empty:
        raise ValueError("base_returns deve contenere almeno un valore")
    scenarios = tuple(scenarios or DEFAULT_SHOCKS)
    target_vol = float(base_series.std(ddof=0)) if scale_to_base_vol else 1.0

    records: list[dict[str, float | str | int]] = []
    for scenario in scenarios:
        path = scenario.returns
        if scale_to_base_vol:
            path = _scale_scenario(path, target_vol)
        max_dd = _scenario_max_drawdown(path)
        cagr = _scenario_cagr(path, periods_per_year=periods_per_year)
        records.append(
            {
                "scenario": scenario.name,
                "length": len(path),
                "max_drawdown": max_dd,
                "cagr": cagr,
            }
        )
    frame = pd.DataFrame.from_records(records)
    frame.sort_values("max_drawdown", inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame
