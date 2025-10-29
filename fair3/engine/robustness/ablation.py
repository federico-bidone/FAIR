"""Utilità per studi di ablation nel laboratorio di robustezza.

Il modulo fornisce funzioni per costruire e rieseguire portafogli con feature
disattivate, così da quantificare l'impatto di ciascun interruttore di
governance. I commenti esplicitano ogni passaggio così che il workflow risulti
immediatamente leggibile agli analisti che eseguono audit in italiano.
"""

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
# L'elenco raccoglie gli interruttori storicamente più critici per FAIR-III.
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
    """Costruisce e normalizza il dizionario di flag partendo dalle feature note.

    Il dizionario risultante è sempre completo (tutte le feature sono presenti)
    ed è composto da chiavi ``str``. Questo evita sorprese quando i flag
    provengono da configurazioni YAML o da CLI dove potrebbero essere tipizzati
    in modo eterogeneo.
    """

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
    """Esegue l'ablation, spegnendo ogni feature e confrontando le metriche.

    Args:
        runner: Callback che calcola le metriche di performance ricevendo in
            input un dizionario di flag ``feature -> bool``.
        features: Sequenza di nomi delle feature da includere nello studio;
            ``None`` usa :data:`DEFAULT_FEATURES`.
        base_flags: Mappa opzionale con lo stato iniziale dei flag per la
            generazione della baseline.

    Returns:
        :class:`AblationOutcome` con la serie baseline e la tabella dei delta
        per ogni feature/ metrica.

    Raises:
        ValueError: Quando l'elenco feature è vuoto, il runner restituisce
            metriche inconsistenti oppure nessuna metrica.
    """

    feature_list = tuple(DEFAULT_FEATURES if features is None else features)
    if not feature_list:
        raise ValueError("features deve contenere almeno un elemento")

    # Calcoliamo la baseline con tutti i flag attivi per avere un riferimento.
    # Questa baseline costituirà il punto di confronto per ogni ablation.
    flags = _normalise_flags(feature_list, base_flags)
    baseline_metrics = pd.Series(runner(flags), dtype="float64")
    if baseline_metrics.empty:
        raise ValueError("runner deve restituire almeno una metrica")

    rows: list[dict[str, object]] = []
    for feature in feature_list:
        # Copiamo i flag per non mutare l'input del passo successivo e
        # impostiamo a ``False`` la feature in esame.
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
