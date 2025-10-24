from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import pandas as pd

__all__ = [
    "DEFAULT_FEATURES",
    "AblationOutcome",
    "run_ablation_study",
]

EvaluationCallback = Callable[[Mapping[str, bool]], Mapping[str, float]]

DEFAULT_FEATURES: tuple[str, ...] = (
    "bl_fallback",
    "sigma_psd",
    "drift_trigger",
    "meta_to_te",
    "regime_tilt",
    "no_trade_rule",
)


@dataclass(frozen=True)
class AblationOutcome:
    """Container storing ablation results."""

    baseline: pd.Series
    table: pd.DataFrame


def _normalise_flags(
    features: Sequence[str],
    base_flags: Mapping[str, bool] | None = None,
) -> dict[str, bool]:
    flags = {name: True for name in features}
    if base_flags:
        for key, value in base_flags.items():
            flags[str(key)] = bool(value)
    return flags


def run_ablation_study(
    runner: EvaluationCallback,
    *,
    features: Sequence[str] | None = None,
    base_flags: Mapping[str, bool] | None = None,
) -> AblationOutcome:
    """Execute an ablation study by toggling each feature off in turn."""

    feature_list = tuple(features or DEFAULT_FEATURES)
    if not feature_list:
        raise ValueError("features must contain at least one entry")

    flags = _normalise_flags(feature_list, base_flags)
    baseline_metrics = pd.Series(runner(flags), dtype="float64")
    if baseline_metrics.empty:
        raise ValueError("runner must return at least one metric")

    rows: list[dict[str, object]] = []
    for feature in feature_list:
        variant_flags = dict(flags)
        variant_flags[feature] = False
        variant_metrics = pd.Series(runner(variant_flags), dtype="float64")
        if not baseline_metrics.index.equals(variant_metrics.index):
            raise ValueError("runner must return consistent metric keys")
        for metric_name, baseline_value in baseline_metrics.items():
            variant_value = float(variant_metrics[metric_name])
            rows.append(
                {
                    "feature": feature,
                    "metric": metric_name,
                    "baseline": float(baseline_value),
                    "variant": variant_value,
                    "delta": float(variant_value - baseline_value),
                }
            )
    table = pd.DataFrame.from_records(rows)
    return AblationOutcome(baseline=baseline_metrics, table=table)
