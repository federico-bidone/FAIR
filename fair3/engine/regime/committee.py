"""Committee helpers for the enhanced regime probability engine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

try:  # pragma: no cover - optional dependency shim
    from hmmlearn.hmm import GaussianHMM

    _HAS_HMMLEARN = True
except ModuleNotFoundError:  # pragma: no cover - fallback
    GaussianHMM = None  # type: ignore[assignment]
    _HAS_HMMLEARN = False

from fair3.engine.logging import setup_logger
from fair3.engine.regime.hysteresis import apply_hysteresis

LOG = setup_logger(__name__)


@dataclass(frozen=True)
class CommitteeWeights:
    """Weights applied to each regime committee component.

    Attributes:
      hmm: Weight assigned to the HMM over market returns.
      volatility: Weight assigned to the volatility HSMM component.
      macro: Weight assigned to the macro slowdown trigger.
    """

    hmm: float = 0.5
    volatility: float = 0.3
    macro: float = 0.2

    def normalised(self) -> tuple[float, float, float]:
        """Return the tuple of weights normalised to sum to one.

        Returns:
          Tuple ``(w_hmm, w_volatility, w_macro)`` that sums to one.

        Raises:
          ValueError: If the aggregate weight is not strictly positive.
        """

        total = float(self.hmm + self.volatility + self.macro)
        if total <= 0.0:
            msg = "Committee weights must sum to a positive value."
            raise ValueError(msg)
        return (self.hmm / total, self.volatility / total, self.macro / total)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object] | None) -> CommitteeWeights:
        """Create weights from an arbitrary mapping.

        Args:
          payload: Mapping with optional ``hmm``, ``volatility`` and ``macro`` keys.

        Returns:
          :class:`CommitteeWeights` populated with the provided values or defaults.
        """

        if not payload:
            return cls()
        return cls(
            hmm=float(payload.get("hmm", cls.hmm)),
            volatility=float(payload.get("volatility", cls.volatility)),
            macro=float(payload.get("macro", cls.macro)),
        )


def _coerce_mapping(payload: object) -> dict[str, Any]:
    """Convert arbitrary payloads (e.g. pydantic models) into dictionaries."""

    if payload is None:
        return {}
    if isinstance(payload, Mapping):
        return dict(payload)
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump(by_alias=True))  # type: ignore[call-arg]
    if hasattr(payload, "dict"):
        return dict(payload.dict())  # type: ignore[call-arg]
    return {}


def _extract_section(panel: pd.DataFrame, field: str) -> pd.DataFrame:
    """Return the panel section for ``field`` handling multi-index columns."""

    if panel.empty:
        return pd.DataFrame()
    if isinstance(panel.columns, pd.MultiIndex) and field in panel.columns.get_level_values(0):
        section = panel.xs(field, axis=1, level=0, drop_level=True)
        if isinstance(section, pd.Series):
            return section.to_frame(name=str(section.name))
        return section
    if field in panel.columns:
        column = panel[field]
        if isinstance(column, pd.Series):
            return column.to_frame(name=str(field))
        if isinstance(column, pd.DataFrame):
            return column
        return pd.DataFrame({field: column})
    return pd.DataFrame()


def _ensure_datetime_index(index: pd.Index) -> pd.DatetimeIndex:
    """Convert an arbitrary index to a :class:`~pandas.DatetimeIndex`."""

    if isinstance(index, pd.DatetimeIndex):
        return index
    return pd.to_datetime(index)


def _fit_hmm(series: pd.Series, seed: int) -> tuple[pd.Series, pd.Series]:
    """Fit a two-state Gaussian HMM returning crisis probabilities and states."""

    if series.empty:
        empty_index = pd.Index(series.index, dtype="datetime64[ns]")
        return pd.Series(dtype=float, index=empty_index), pd.Series(dtype=float, index=empty_index)

    series = series.sort_index().astype(float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    index = _ensure_datetime_index(series.index)
    if not _HAS_HMMLEARN:
        centred = series - series.mean()
        scale = float(series.std()) or 1.0
        z_score = centred / scale
        probs = pd.Series(1.0 / (1.0 + np.exp(z_score.to_numpy())), index=index)
        states = (probs > 0.5).astype(float)
        return probs.clip(0.0, 1.0), states

    values = series.to_numpy(dtype="float64").reshape(-1, 1)
    if np.ptp(values) < 1e-8:
        baseline = np.full(len(values), 0.05, dtype="float64")
        return pd.Series(baseline, index=index), pd.Series(np.zeros(len(values)), index=index)

    rng = np.random.default_rng(seed)
    random_state = int(rng.integers(0, 2**31 - 1))
    model = GaussianHMM(
        n_components=2,
        covariance_type="diag",
        n_iter=200,
        random_state=random_state,
    )
    try:
        model.fit(values)
        posterior = model.predict_proba(values)
        states = model.predict(values)
    except ValueError:
        LOG.exception("GaussianHMM fitting failed; reverting to fixed probability prior")
        baseline = np.full(len(values), 0.1, dtype="float64")
        return pd.Series(baseline, index=index), pd.Series(np.zeros(len(values)), index=index)

    means = model.means_.reshape(-1)
    crisis_idx = int(np.argmin(means))
    probs = posterior[:, crisis_idx]
    state = (states == crisis_idx).astype(float)
    return pd.Series(probs, index=index), pd.Series(state, index=index)


def _smooth_states(states: np.ndarray, min_duration: int) -> np.ndarray:
    """Impose a minimum dwell time on discrete state sequences."""

    if min_duration <= 1 or states.size == 0:
        return states
    corrected = states.copy()
    start = 0
    current = states[0]
    for idx in range(1, states.size + 1):
        end_of_segment = idx == states.size or states[idx] != current
        if not end_of_segment:
            continue
        segment_len = idx - start
        if segment_len < min_duration and start > 0:
            corrected[start:idx] = corrected[start - 1]
        if idx < states.size:
            start = idx
            current = states[idx]
    return corrected


def _volatility_probabilities(
    vol: pd.Series,
    config: Mapping[str, Any],
    seed: int,
) -> tuple[pd.Series, pd.Series]:
    """Compute HSMM-inspired volatility stress probabilities."""

    if vol.empty:
        index = _ensure_datetime_index(vol.index)
        empty = pd.Series(dtype=float, index=index)
        return empty, empty

    vol = vol.sort_index().astype(float).replace([np.inf, -np.inf], np.nan).ffill()
    index = _ensure_datetime_index(vol.index)
    window = max(1, int(config.get("window", 63)))
    smoothed = vol.rolling(window=window, min_periods=max(5, window // 3)).mean()
    smoothed = smoothed.bfill()
    log_vol = np.log1p(smoothed.clip(lower=1e-6))

    probs, states = _fit_hmm(pd.Series(log_vol, index=index), seed)
    min_duration = max(1, int(config.get("min_duration", 5)))
    smoothing = max(1, int(config.get("smoothing", 5)))

    state_array = _smooth_states(states.to_numpy(dtype=int), min_duration)
    state_series = pd.Series(state_array.astype(float), index=index)
    stress_prob = probs.rolling(window=smoothing, min_periods=1).mean().clip(0.0, 1.0)
    return stress_prob, state_series


def _macro_probabilities(macro: pd.DataFrame, config: Mapping[str, Any]) -> pd.Series:
    """Aggregate macro slowdown triggers into a probability measure."""

    if macro.empty:
        return pd.Series(dtype=float)

    macro = macro.sort_index().astype(float).replace([np.inf, -np.inf], np.nan).ffill()
    macro = macro.dropna(how="all")
    if macro.empty:
        return pd.Series(dtype=float)

    weights = {
        "inflation_weight": float(config.get("inflation_weight", 0.4)),
        "pmi_weight": float(config.get("pmi_weight", 0.35)),
        "real_rate_weight": float(config.get("real_rate_weight", 0.25)),
    }
    smoothing = max(1, int(config.get("smoothing", 3)))
    pmi_threshold = float(config.get("pmi_threshold", 50.0))
    real_rate_threshold = float(config.get("real_rate_threshold", 0.0))

    contributions: list[pd.Series] = []
    weight_total = 0.0

    if "inflation_yoy" in macro.columns and weights["inflation_weight"] > 0.0:
        inflation = macro["inflation_yoy"].astype(float)
        baseline_window = max(smoothing * 3, 6)
        baseline = inflation.rolling(window=baseline_window, min_periods=1).mean()
        deviation = inflation - baseline
        infl_score = 0.5 * (1.0 + np.tanh(deviation / 1.5))
        contributions.append(weights["inflation_weight"] * infl_score)
        weight_total += weights["inflation_weight"]

    if "pmi" in macro.columns and weights["pmi_weight"] > 0.0:
        pmi = macro["pmi"].astype(float)
        pmi_score = 0.5 * (1.0 + np.tanh((pmi_threshold - pmi) / 5.0))
        contributions.append(weights["pmi_weight"] * pmi_score)
        weight_total += weights["pmi_weight"]

    if "real_rate" in macro.columns and weights["real_rate_weight"] > 0.0:
        real_rate = macro["real_rate"].astype(float)
        real_rate_score = 0.5 * (1.0 + np.tanh((real_rate - real_rate_threshold) / 1.5))
        contributions.append(weights["real_rate_weight"] * real_rate_score)
        weight_total += weights["real_rate_weight"]

    if not contributions or weight_total <= 0.0:
        return pd.Series(0.5, index=_ensure_datetime_index(macro.index))

    combined = sum(contributions) / weight_total
    combined = combined.rolling(window=smoothing, min_periods=1).mean().clip(0.0, 1.0)
    combined.index = _ensure_datetime_index(combined.index)
    return combined


def regime_probability(
    panel: pd.DataFrame,
    cfg: Mapping[str, Any] | object,
    seed: int,
) -> pd.DataFrame:
    """Compute crisis probabilities using HMM, volatility HSMM and macro triggers.

    Args:
      panel: Panel containing at least a ``returns`` section (wide DataFrame) and
        optionally ``volatility`` and ``macro`` sections. Each section should be
        aligned on a PIT index without look-ahead.
      cfg: Threshold configuration dictionary (or pydantic object) containing the
        ``regime`` section defined in ``configs/thresholds.yml``.
      seed: Deterministic seed used for the stochastic HMM initialisation.

    Returns:
      DataFrame indexed by timestamp with columns ``p_crisis``, ``p_hmm``,
      ``p_volatility``, ``p_macro``, ``hmm_state``, ``vol_state``,
      ``macro_trigger`` and ``regime_flag``.
    """

    if panel.empty:
        return pd.DataFrame(
            columns=[
                "p_crisis",
                "p_hmm",
                "p_volatility",
                "p_macro",
                "hmm_state",
                "vol_state",
                "macro_trigger",
                "regime_flag",
            ]
        )

    panel = panel.sort_index()
    config = _coerce_mapping(cfg)
    regime_cfg = _coerce_mapping(config.get("regime", config))
    thresholds = {
        "on": float(regime_cfg.get("on", 0.65)),
        "off": float(regime_cfg.get("off", 0.45)),
        "dwell_days": int(regime_cfg.get("dwell_days", 20)),
        "cooldown_days": int(regime_cfg.get("cooldown_days", 10)),
        "activate_streak": int(regime_cfg.get("activate_streak", 3)),
        "deactivate_streak": int(regime_cfg.get("deactivate_streak", 3)),
    }
    weights_cfg = _coerce_mapping(regime_cfg.get("weights"))
    weights = CommitteeWeights.from_mapping(weights_cfg)
    vol_cfg = _coerce_mapping(regime_cfg.get("volatility"))
    macro_cfg = _coerce_mapping(regime_cfg.get("macro"))

    returns_section = _extract_section(panel, "returns")
    if returns_section.empty:
        LOG.warning("Panel lacks a returns section; regime probability is empty")
        return pd.DataFrame(
            columns=[
                "p_crisis",
                "p_hmm",
                "p_volatility",
                "p_macro",
                "hmm_state",
                "vol_state",
                "macro_trigger",
                "regime_flag",
            ]
        )

    returns_section = returns_section.dropna(how="all")
    returns_section.index = _ensure_datetime_index(returns_section.index)
    returns_avg = returns_section.mean(axis=1)

    vol_section = _extract_section(panel, "volatility")
    vol_series = vol_section.mean(axis=1) if not vol_section.empty else pd.Series(dtype=float)
    has_volatility = not vol_section.empty
    if has_volatility and not vol_series.empty:
        vol_series.index = _ensure_datetime_index(vol_series.index)
        vol_series = vol_series.dropna()

    macro_section = _extract_section(panel, "macro")
    if not macro_section.empty:
        macro_section.index = _ensure_datetime_index(macro_section.index)
        macro_section = macro_section.dropna(how="all")

    aligned_index = returns_avg.index
    if has_volatility:
        if vol_series.empty:
            aligned_index = pd.DatetimeIndex([], dtype="datetime64[ns]")
        else:
            aligned_index = aligned_index.intersection(vol_series.index)
    if not macro_section.empty:
        aligned_index = aligned_index.intersection(macro_section.index)

    if aligned_index.empty:
        LOG.warning("No overlapping observations across returns/vol/macro for regime engine")
        return pd.DataFrame(
            columns=[
                "p_crisis",
                "p_hmm",
                "p_volatility",
                "p_macro",
                "hmm_state",
                "vol_state",
                "macro_trigger",
                "regime_flag",
            ]
        )

    returns_avg = returns_avg.reindex(aligned_index).fillna(0.0)
    hmm_prob, hmm_state = _fit_hmm(returns_avg, seed)

    if vol_series.empty:
        vol_prob = pd.Series(0.5, index=aligned_index)
        vol_state = pd.Series(0.0, index=aligned_index)
    else:
        aligned_vol = vol_series.reindex(aligned_index).ffill().bfill()
        vol_prob, vol_state = _volatility_probabilities(aligned_vol, vol_cfg, seed + 1)
        vol_prob = vol_prob.reindex(aligned_index).fillna(0.5)
        vol_state = vol_state.reindex(aligned_index).fillna(0.0)

    macro_prob = (
        _macro_probabilities(macro_section.reindex(aligned_index), macro_cfg)
        if not macro_section.empty
        else pd.Series(0.5, index=aligned_index)
    )
    macro_prob = macro_prob.reindex(aligned_index).fillna(0.5)

    w_hmm, w_vol, w_macro = weights.normalised()
    combined = (
        w_hmm * hmm_prob.reindex(aligned_index).fillna(0.05)
        + w_vol * vol_prob
        + w_macro * macro_prob
    ).clip(0.0, 1.0)

    regime_flag = apply_hysteresis(
        combined,
        thresholds["on"],
        thresholds["off"],
        thresholds["dwell_days"],
        thresholds["cooldown_days"],
        activate_streak=thresholds["activate_streak"],
        deactivate_streak=thresholds["deactivate_streak"],
    )

    result = pd.DataFrame(
        {
            "p_crisis": combined,
            "p_hmm": hmm_prob.reindex(aligned_index).fillna(0.05),
            "p_volatility": vol_prob,
            "p_macro": macro_prob,
            "hmm_state": hmm_state.reindex(aligned_index).fillna(0.0),
            "vol_state": vol_state.reindex(aligned_index).fillna(0.0),
            "macro_trigger": macro_prob,
            "regime_flag": regime_flag,
        }
    )
    LOG.info(
        "Regime engine completed on %s observations (p_crisis median=%.3f)",
        len(result),
        float(result["p_crisis"].median()) if not result.empty else float("nan"),
    )
    return result


def crisis_probability(
    returns: pd.DataFrame,
    vol: pd.Series,
    macro: pd.DataFrame,
    weights: CommitteeWeights | None = None,
) -> pd.Series:
    """Compatibility wrapper returning the combined crisis probability series.

    Args:
      returns: Return panel indexed by timestamp.
      vol: Volatility proxy aligned with ``returns``.
      macro: Macro indicators aligned with ``returns``.
      weights: Optional committee weights overriding the defaults.

    Returns:
      Series with the crisis probability in ``[0, 1]``.
    """

    weights = weights or CommitteeWeights()
    panel_parts = []
    if not returns.empty:
        panel_parts.append(pd.concat({"returns": returns}, axis=1))
    if not vol.empty:
        panel_parts.append(pd.concat({"volatility": vol.to_frame(name="vol")}, axis=1))
    if not macro.empty:
        panel_parts.append(pd.concat({"macro": macro}, axis=1))
    panel = pd.concat(panel_parts, axis=1) if panel_parts else pd.DataFrame()
    result = regime_probability(panel, {"regime": {"weights": weights.__dict__}}, seed=0)
    return result["p_crisis"] if "p_crisis" in result else pd.Series(dtype=float)


__all__ = [
    "CommitteeWeights",
    "crisis_probability",
    "regime_probability",
]
