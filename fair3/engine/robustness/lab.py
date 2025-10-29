"""Coordinamento delle analisi di robustezza per FAIR-III.

Il laboratorio di robustezza esegue in sequenza bootstrap, scenari storici e
analisi di ablation opzionali. Il modulo mira a rendere espliciti i passaggi
per permettere al team di controllo di comprendere e riprodurre facilmente i
workflow; le docstring in italiano descrivono parametri, artefatti prodotti e
logica di gestione dei seed.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from fair3.engine.robustness.ablation import (
    DEFAULT_FEATURES,
    run_ablation_study,
)
from fair3.engine.robustness.bootstrap import RobustnessGates, block_bootstrap_metrics
from fair3.engine.robustness.scenarios import ShockScenario, replay_shocks
from fair3.engine.utils.io import artifact_path, ensure_dir, write_json
from fair3.engine.utils.rand import generator_from_seed, spawn_child_rng

# Impostiamo il backend ``Agg`` così da poter generare PDF anche in ambienti
# headless (es. CI o container senza display server).
plt.switch_backend("Agg")

__all__ = [
    "RobustnessConfig",
    "RobustnessArtifacts",
    "run_robustness_lab",
]


@dataclass(frozen=True)
class RobustnessConfig:
    """Parametri che regolano il laboratorio di robustezza."""

    block_size: int = 60
    draws: int = 1_000
    periods_per_year: int = 252
    alpha: float = 0.95
    max_drawdown_threshold: float = -0.25
    cagr_target: float = 0.03
    scenario_scale_to_vol: bool = True
    features: Sequence[str] = DEFAULT_FEATURES
    output_dir: Path | None = None
    stream: str = "robustness"


@dataclass(frozen=True)
class RobustnessArtifacts:
    """Percorsi generati da :func:`run_robustness_lab`."""

    bootstrap_csv: Path
    scenarios_csv: Path
    summary_json: Path
    report_pdf: Path
    ablation_csv: Path | None = None


def _render_pdf(
    bootstrap: pd.DataFrame,
    scenarios: pd.DataFrame,
    gates: RobustnessGates,
    *,
    path: Path,
) -> Path:
    """Costruisce un PDF con istogramma bootstrap e riepilogo degli scenari.

    Args:
        bootstrap: DataFrame con le metriche ottenute dal bootstrap.
        scenarios: DataFrame con gli esiti del replay degli shock.
        gates: Risultati dei controlli di robustezza da riportare nel riepilogo.
        path: Percorso finale del PDF da generare.

    Returns:
        Percorso del PDF scritto su disco, utile per logging a valle.
    """

    fig, axes = plt.subplots(2, 1, figsize=(8.0, 10.0))

    ax0 = axes[0]
    ax0.hist(bootstrap["max_drawdown"], bins=30, color="#4062bb", alpha=0.75)
    ax0.axvline(gates.max_drawdown_threshold, color="#c43c00", linestyle="--", label="Soglia")
    ax0.set_title("Distribuzione drawdown bootstrap")
    ax0.set_xlabel("Max drawdown")
    ax0.set_ylabel("Frequenza")
    ax0.legend()

    ax1 = axes[1]
    ax1.bar(scenarios["scenario"], scenarios["max_drawdown"], color="#2e8b57")
    ax1.set_title("Drawdown per scenario storico")
    ax1.set_ylabel("Max drawdown")
    ax1.tick_params(axis="x", rotation=20)

    summary = (
        f"Prob. superamento soglia: {gates.exceedance_probability:.3f}\n"
        f"CAGR limite inferiore: {gates.cagr_lower_bound:.3%}\n"
        f"Gates superati: {gates.passes()}"
    )
    fig.text(0.02, 0.02, summary, fontsize=10, family="monospace")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    ensure_dir(path.parent)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def run_robustness_lab(
    returns: Iterable[float],
    *,
    config: RobustnessConfig | None = None,
    seed: int | None = None,
    scenarios: Sequence[ShockScenario] | None = None,
    ablation_runner: Callable[..., Mapping[str, float]] | None = None,
    base_flags: Mapping[str, bool] | None = None,
) -> tuple[RobustnessArtifacts, RobustnessGates]:
    """Esegue bootstrap, scenari e (opzionalmente) ablation sui rendimenti.

    Il laboratorio crea una struttura di cartelle (quando non fornita) e salva
    tutti gli artefatti su disco per facilitare audit e reportistica.

    Args:
        returns: Sequenza di rendimenti storici su cui applicare le analisi.
        config: Configurazione del laboratorio; se ``None`` usa i default.
        seed: Seed deterministico condiviso tra bootstrap e ablation.
        scenarios: Shock storici personalizzati da utilizzare; ``None`` usa
            :func:`default_shock_scenarios`.
        ablation_runner: Callback per eseguire lo studio di ablation; se
            assente il passo viene saltato.
        base_flags: Set di flag iniziali passato all'ablation per definire la
            baseline.

    Returns:
        Coppia con gli artefatti generati e i gate di robustezza calcolati.
    """

    cfg = config or RobustnessConfig()
    base_path = cfg.output_dir or artifact_path("robustness", create=True)
    base_path = ensure_dir(base_path)

    parent_rng = generator_from_seed(seed, stream=cfg.stream)
    # Ogni sotto-processo ottiene un generatore figlio per evitare correlazioni
    # tra bootstrap e ablation pur mantenendo riproducibilità globale.
    bootstrap_rng = spawn_child_rng(parent_rng)

    bootstrap_df, gates = block_bootstrap_metrics(
        returns,
        block_size=cfg.block_size,
        draws=cfg.draws,
        periods_per_year=cfg.periods_per_year,
        alpha=cfg.alpha,
        max_drawdown_threshold=cfg.max_drawdown_threshold,
        cagr_target=cfg.cagr_target,
        seed=bootstrap_rng,
    )

    bootstrap_csv = base_path / "bootstrap.csv"
    bootstrap_df.to_csv(bootstrap_csv, index=False)

    scenario_df = replay_shocks(
        returns,
        scenarios=scenarios,
        scale_to_base_vol=cfg.scenario_scale_to_vol,
        periods_per_year=cfg.periods_per_year,
    )
    scenarios_csv = base_path / "scenarios.csv"
    scenario_df.to_csv(scenarios_csv, index=False)

    summary_payload = {
        "max_drawdown_threshold": cfg.max_drawdown_threshold,
        "cagr_target": cfg.cagr_target,
        "exceedance_probability": gates.exceedance_probability,
        "cagr_lower_bound": gates.cagr_lower_bound,
        "alpha": cfg.alpha,
        "passes": gates.passes(),
    }
    summary_json = base_path / "summary.json"
    write_json(summary_payload, summary_json)

    report_pdf = base_path / "robustness_report.pdf"
    _render_pdf(bootstrap_df, scenario_df, gates, path=report_pdf)

    ablation_csv: Path | None = None
    if ablation_runner is not None:
        ablation_rng = spawn_child_rng(parent_rng)

        signature = inspect.signature(ablation_runner)

        def runner(flags: Mapping[str, bool]) -> Mapping[str, float]:
            """Adatta la callback utenti accettando opzionalmente seed o rng.

            Consente di supportare più API utente senza duplicare logica:
            se la callback espone ``rng`` riceve il generatore figlio, mentre
            con ``seed`` viene fornito un intero determinato in modo
            deterministico.
            """

            bound_kwargs: dict[str, object] = {}
            if "rng" in signature.parameters:
                bound_kwargs["rng"] = ablation_rng
            elif "seed" in signature.parameters:
                bound_kwargs["seed"] = int(ablation_rng.integers(0, 2**32 - 1))
            return ablation_runner(flags, **bound_kwargs)

        ablation = run_ablation_study(
            runner,
            features=cfg.features,
            base_flags=base_flags,
        )
        ablation_csv = base_path / "ablation.csv"
        ablation.table.to_csv(ablation_csv, index=False)

    artifacts = RobustnessArtifacts(
        bootstrap_csv=bootstrap_csv,
        scenarios_csv=scenarios_csv,
        summary_json=summary_json,
        report_pdf=report_pdf,
        ablation_csv=ablation_csv,
    )
    return artifacts, gates
