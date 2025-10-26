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

# Le feature rappresentano gli interruttori di governance che vogliamo
# disattivare uno alla volta per misurare l'impatto su Sharpe, drawdown ecc.
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
    """Risultato dell'ablation: serie baseline e tabella con le variazioni."""

    baseline: pd.Series
    table: pd.DataFrame


def _normalise_flags(
    features: Sequence[str],
    base_flags: Mapping[str, bool] | None = None,
) -> dict[str, bool]:
    """Costruisce il dizionario di flag partendo dalle feature note."""

    flags = {name: True for name in features}
    if base_flags:
        # Normalizziamo le chiavi esterne in stringa per evitare incongruenze
        # quando arrivano da YAML o configurazioni CLI.
        for key, value in base_flags.items():
            flags[str(key)] = bool(value)
    return flags


def run_ablation_study(
    runner: EvaluationCallback,
    *,
    features: Sequence[str] | None = None,
    base_flags: Mapping[str, bool] | None = None,
) -> AblationOutcome:
    """Esegue l'ablation, spegnendo ogni feature e confrontando le metriche."""

    feature_list = tuple(DEFAULT_FEATURES if features is None else features)
    if not feature_list:
        raise ValueError("features deve contenere almeno un elemento")

    # Calcoliamo la baseline con tutti i flag attivi per avere un riferimento.
    flags = _normalise_flags(feature_list, base_flags)
    baseline_metrics = pd.Series(runner(flags), dtype="float64")
    if baseline_metrics.empty:
        raise ValueError("runner deve restituire almeno una metrica")

    rows: list[dict[str, object]] = []
    for feature in feature_list:
        variant_flags = dict(flags)
        variant_flags[feature] = False
        variant_metrics = pd.Series(runner(variant_flags), dtype="float64")
        if not baseline_metrics.index.equals(variant_metrics.index):
            raise ValueError("runner deve usare sempre gli stessi nomi di metrica")
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
