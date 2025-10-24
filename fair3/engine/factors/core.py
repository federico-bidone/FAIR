from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from fair3.engine.utils.rand import generator_from_seed

__all__ = [
    "FactorDefinition",
    "FactorLibrary",
    "compute_macro_factors",
]


@dataclass(frozen=True)
class FactorDefinition:
    """Metadata describing an individual macro factor series."""

    name: str
    expected_sign: int
    description: str

    def __post_init__(self) -> None:  # pragma: no cover - dataclass guard
        if self.expected_sign not in (-1, 1):
            msg = "expected_sign must be -1 or 1"
            raise ValueError(msg)


class FactorLibrary:
    """Generate macro factor premia from the PIT total-return panel."""

    REQUIRED_FEATURES = {"lag_ma_5", "lag_ma_21", "lag_vol_21"}

    def __init__(
        self,
        returns: pd.DataFrame,
        features: pd.DataFrame,
        *,
        macro: pd.DataFrame | None = None,
        top_quantile: float = 0.3,
        bottom_quantile: float = 0.3,
        min_assets: int = 5,
        seed: int | None = None,
    ) -> None:
        self._returns = self._prepare_returns(returns)
        self._features = self._prepare_features(features)
        self._macro = self._prepare_macro(macro)
        self._top_q = float(top_quantile)
        self._bot_q = float(bottom_quantile)
        self._min_assets = int(min_assets)
        self._rng = generator_from_seed(seed, stream="factors")
        self._definitions: list[FactorDefinition] = []
        if not 0 < self._bot_q < 0.5 or not 0 < self._top_q < 0.5:
            msg = "Quantiles must be in (0, 0.5)."
            raise ValueError(msg)
        if self._top_q + self._bot_q > 0.9:
            msg = "Quantile spread too narrow; reduce top/bottom quantiles."
            raise ValueError(msg)

    # ------------------------------------------------------------------
    @staticmethod
    def _prepare_returns(frame: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(frame.index, pd.MultiIndex) or frame.index.nlevels != 2:
            raise TypeError("returns must be indexed by (date, symbol)")
        if "ret" not in frame.columns:
            raise KeyError("returns DataFrame must contain 'ret' column")
        return frame[["ret"]].copy()

    @classmethod
    def _prepare_features(cls, frame: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(frame.index, pd.MultiIndex) or frame.index.nlevels != 2:
            raise TypeError("features must be indexed by (date, symbol)")
        missing = cls.REQUIRED_FEATURES - set(frame.columns)
        if missing:
            msg = f"features missing required columns: {sorted(missing)}"
            raise KeyError(msg)
        return frame[list(cls.REQUIRED_FEATURES)].copy()

    @staticmethod
    def _prepare_macro(frame: pd.DataFrame | None) -> pd.DataFrame | None:
        if frame is None:
            return None
        if not isinstance(frame.index, pd.DatetimeIndex):
            raise TypeError("macro frame must be indexed by DatetimeIndex")
        ordered = frame.sort_index()
        return ordered

    # ------------------------------------------------------------------
    @property
    def definitions(self) -> list[FactorDefinition]:
        return list(self._definitions)

    # ------------------------------------------------------------------
    def compute(self) -> pd.DataFrame:
        returns = self._returns
        features = self._features
        panel = returns.join(features, how="left")
        if panel.empty:
            raise ValueError("Panel is empty; run ETL before computing factors")

        lag_vol = panel["lag_vol_21"].replace(0.0, np.nan).ffill()
        inv_vol = 1.0 / (lag_vol.replace(0.0, np.nan))
        inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        diff_ma = panel["lag_ma_5"] - panel["lag_ma_21"]
        stability = panel["lag_ma_21"] / (panel["lag_vol_21"] + 1e-8)

        signals: Mapping[str, pd.Series] = {
            "global_momentum": panel["lag_ma_21"],
            "short_term_reversal": -panel["lag_ma_5"],
            "value_rebound": -panel["lag_ma_21"],
            "carry_roll_down": diff_ma,
            "quality_low_vol": inv_vol,
            "defensive_stability": stability,
            "liquidity_risk": panel["lag_vol_21"],
            "growth_cycle": panel["lag_ma_5"],
        }

        factors: dict[str, pd.Series] = {
            "global_mkt": self._equal_weight_market(),
        }

        for name, signal in signals.items():
            factors[name] = self._quantile_spread(signal, returns["ret"], name=name)

        factors.update(self._macro_overlays())

        ordered_names = [
            "global_mkt",
            "global_momentum",
            "short_term_reversal",
            "value_rebound",
            "carry_roll_down",
            "quality_low_vol",
            "defensive_stability",
            "liquidity_risk",
            "growth_cycle",
            "inflation_hedge",
            "rates_beta",
        ]

        aligned = self._align_columns(factors, ordered_names)
        self._definitions = _build_definitions()
        return aligned

    # ------------------------------------------------------------------
    def _equal_weight_market(self) -> pd.Series:
        ret = self._returns["ret"].unstack(level=1)
        series = ret.mean(axis=1).fillna(0.0)
        return series.rename("global_mkt")

    def _quantile_spread(self, signal: pd.Series, returns: pd.Series, *, name: str) -> pd.Series:
        idx_dates = signal.index.get_level_values(0).unique()
        out = []
        for dt in idx_dates:
            sig_slice = signal.xs(dt, level=0)
            ret_slice = returns.xs(dt, level=0)
            frame = pd.DataFrame({"signal": sig_slice, "ret": ret_slice}).dropna()
            if frame.empty:
                out.append(0.0)
                continue
            if frame["signal"].nunique() <= max(1, int(self._min_assets * 0.2)):
                jitter = self._rng.normal(0.0, 1e-9, size=len(frame))
                frame["signal"] = frame["signal"] + jitter
            if len(frame) < self._min_assets:
                out.append(0.0)
                continue
            hi = frame["signal"].quantile(1 - self._top_q)
            lo = frame["signal"].quantile(self._bot_q)
            long_mask = frame["signal"] >= hi
            short_mask = frame["signal"] <= lo
            if long_mask.sum() == 0 or short_mask.sum() == 0:
                out.append(0.0)
                continue
            long_ret = frame.loc[long_mask, "ret"].mean()
            short_ret = frame.loc[short_mask, "ret"].mean()
            out.append(float(long_ret - short_ret))
        series = pd.Series(out, index=idx_dates, name=name)
        return series.fillna(0.0)

    def _macro_overlays(self) -> dict[str, pd.Series]:
        index = self._returns.index.get_level_values(0).unique()
        if self._macro is None or self._macro.empty:
            zero = pd.Series(0.0, index=index)
            return {
                "inflation_hedge": zero.rename("inflation_hedge"),
                "rates_beta": zero.rename("rates_beta"),
            }

        macro = self._macro.reindex(index).ffill().bfill().fillna(0.0)
        inflation = macro.get("inflation", pd.Series(0.0, index=index))
        policy_rate = macro.get("policy_rate", pd.Series(0.0, index=index))

        inflation_factor = inflation.diff().fillna(0.0)
        rates_factor = -policy_rate.diff().fillna(0.0)

        return {
            "inflation_hedge": inflation_factor.rename("inflation_hedge"),
            "rates_beta": rates_factor.rename("rates_beta"),
        }

    @staticmethod
    def _align_columns(factors: Mapping[str, pd.Series], order: Iterable[str]) -> pd.DataFrame:
        columns: dict[str, pd.Series] = {}
        for name in order:
            series = factors.get(name)
            if series is None:
                series = pd.Series(0.0, index=next(iter(factors.values())).index, name=name)
            columns[name] = series
        frame = pd.concat(columns.values(), axis=1)
        frame = frame.sort_index()
        return frame


def compute_macro_factors(
    returns: pd.DataFrame,
    features: pd.DataFrame,
    *,
    macro: pd.DataFrame | None = None,
    seed: int | None = None,
) -> tuple[pd.DataFrame, list[FactorDefinition]]:
    """Convenience helper returning macro factor series and metadata."""

    library = FactorLibrary(returns, features, macro=macro, seed=seed)
    factors = library.compute()
    return factors, library.definitions


def _build_definitions() -> list[FactorDefinition]:
    return [
        FactorDefinition(
            name="global_mkt",
            expected_sign=1,
            description="Equally weighted market factor capturing broad beta.",
        ),
        FactorDefinition(
            name="global_momentum",
            expected_sign=1,
            description="Long high trailing log-return assets versus low (12M proxy).",
        ),
        FactorDefinition(
            name="short_term_reversal",
            expected_sign=1,
            description="Contrarian tilt favouring recent underperformers over winners.",
        ),
        FactorDefinition(
            name="value_rebound",
            expected_sign=1,
            description="Value-style mean reversion using depressed lagged momentum as proxy.",
        ),
        FactorDefinition(
            name="carry_roll_down",
            expected_sign=1,
            description="Carry premium approximated via 5d-21d momentum spread.",
        ),
        FactorDefinition(
            name="quality_low_vol",
            expected_sign=1,
            description="Preference for low realised volatility exposures.",
        ),
        FactorDefinition(
            name="defensive_stability",
            expected_sign=1,
            description="Stability tilt emphasising strong momentum per unit risk.",
        ),
        FactorDefinition(
            name="liquidity_risk",
            expected_sign=1,
            description="Liquidity premium proxy via high minus low volatility cohort.",
        ),
        FactorDefinition(
            name="growth_cycle",
            expected_sign=1,
            description="Growth tilt emphasising improving short-term returns.",
        ),
        FactorDefinition(
            name="inflation_hedge",
            expected_sign=1,
            description="Macro overlay tracking positive surprises in inflation data.",
        ),
        FactorDefinition(
            name="rates_beta",
            expected_sign=-1,
            description="Duration-sensitive tilt benefitting when policy rates fall.",
        ),
    ]
