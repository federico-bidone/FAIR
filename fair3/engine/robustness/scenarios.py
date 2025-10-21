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
    """Container for stylised historical shock return paths."""

    name: str
    returns: np.ndarray


def _scenario_max_drawdown(path: np.ndarray) -> float:
    wealth = np.cumprod(1.0 + path)
    if np.any(wealth <= 0):
        return -1.0
    peaks = np.maximum.accumulate(wealth)
    drawdowns = wealth / peaks - 1.0
    return float(np.min(drawdowns))


def _scenario_cagr(path: np.ndarray, *, periods_per_year: int) -> float:
    total_return = float(np.prod(1.0 + path))
    n_obs = path.shape[0]
    if n_obs == 0 or total_return <= 0:
        return -1.0
    years = n_obs / periods_per_year
    if years <= 0:
        return -1.0
    return float(total_return ** (1.0 / years) - 1.0)


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
    """Return the packaged historical shock scenarios."""

    return DEFAULT_SHOCKS


def _scale_scenario(returns: np.ndarray, target_vol: float) -> np.ndarray:
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
    """Replay stylised shock scenarios using the volatility of ``base_returns``."""

    base_series = pd.Series(base_returns, dtype="float64")
    if base_series.empty:
        raise ValueError("base_returns must contain observations")
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
