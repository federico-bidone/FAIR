"""Pipeline di ottimizzazione dei pesi fattoriali con commenti italiani.

Questo modulo coordina il caricamento degli artefatti di stima, la generazione
dei portafogli singoli, la combinazione meta e la raccolta dei log di audit. La
verbosità è volutamente elevata per chiarire ogni trasformazione effettuata.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.allocators import (
    fit_meta_weights,
    generator_A,
    generator_B_hrp,
    generator_C_dro_closed,
    generator_D_cvar_erc,
    risk_contributions,
)
from fair3.engine.reporting.audit import run_audit_snapshot
from fair3.engine.utils.io import artifact_path, read_yaml
from fair3.engine.utils.logging import get_stream_logger
from fair3.engine.utils.rand import DEFAULT_SEED_PATH

LOG = get_stream_logger(__name__)


@dataclass(slots=True)
class OptimizePipelineResult:
    """Risultato strutturato prodotto da :func:`run_optimization_pipeline`."""

    allocation_path: Path
    generator_paths: Mapping[str, Path]
    meta_weights_path: Path | None
    diagnostics_path: Path


def _load_mu_sigma(artifacts_root: Path | None) -> tuple[pd.Series, np.ndarray]:
    """Carica vettore dei rendimenti attesi e matrice di covarianza."""

    mu_path = artifact_path("estimates", "mu_post.csv", root=artifacts_root)
    sigma_path = artifact_path("estimates", "sigma.npy", root=artifacts_root)
    if not mu_path.exists() or not sigma_path.exists():
        missing = [p for p in (mu_path, sigma_path) if not p.exists()]
        message = ", ".join(str(p) for p in missing)
        raise FileNotFoundError(
            "Artefatti di stima mancanti. Eseguire `fair3 estimate` prima dell'ottimizzazione."
            f" Mancanti: {message}"
        )
    LOG.debug("Carico mu e sigma da %s e %s", mu_path, sigma_path)
    mu_post = pd.read_csv(mu_path, index_col=0).iloc[:, 0]
    sigma = np.load(sigma_path)
    return mu_post, sigma


def _load_factors(artifacts_root: Path | None) -> pd.DataFrame:
    """Carica il pannello di fattori ortogonali usato per gli scenari."""

    path = artifact_path("factors", "factors_orthogonal.parquet", root=artifacts_root)
    if not path.exists():
        raise FileNotFoundError(
            "Artefatto dei fattori mancante. Eseguire `fair3 factors` prima dell'ottimizzazione."
        )
    LOG.debug("Carico fattori ortogonali da %s", path)
    frame = pd.read_parquet(path)
    if not isinstance(frame.index, pd.DatetimeIndex):
        frame.index = pd.to_datetime(frame.index)
    return frame.fillna(0.0)


def _load_configs(params_path: Path, thresholds_path: Path) -> tuple[dict, dict]:
    """Legge i file di configurazione dei parametri e delle soglie."""

    params = read_yaml(params_path)
    thresholds = read_yaml(thresholds_path)
    params = params if isinstance(params, dict) else {}
    thresholds = thresholds if isinstance(thresholds, dict) else {}
    LOG.debug(
        "Parametri caricati da %s e soglie da %s",
        params_path,
        thresholds_path,
    )
    return params, thresholds


def _cluster_indices(n_assets: int, n_clusters: int = 3) -> list[list[int]]:
    """Genera cluster deterministici utilizzati dal generatore ERC."""

    n_clusters = max(1, min(n_clusters, n_assets))
    indices = np.arange(n_assets)
    clusters = np.array_split(indices, n_clusters)
    LOG.debug("Costruiti %s cluster per %s asset", len(clusters), n_assets)
    return [cluster.tolist() for cluster in clusters if cluster.size]


def _run_generator(
    name: str,
    mu_vec: np.ndarray,
    sigma: np.ndarray,
    constraints: dict,
) -> np.ndarray:
    """Esegue il generatore richiesto e restituisce il vettore dei pesi."""

    try:
        if name == "A":
            LOG.info("Avvio del generatore A (Sharpe massimo)")
            return generator_A(mu_vec, sigma, constraints)
        if name == "B":
            LOG.info("Avvio del generatore B (risk parity gerarchico)")
            return generator_B_hrp(sigma)
        if name == "C":
            rho = constraints.get("dro_rho", 0.05)
            LOG.info("Avvio del generatore C (DRO chiuso) con rho=%s", rho)
            return generator_C_dro_closed(mu_vec, sigma, gamma=1.0, rho=rho)
        if name == "D":
            LOG.info("Avvio del generatore D (CVaR-ERC)")
            return generator_D_cvar_erc(mu_vec, sigma, constraints)
        LOG.warning("Generatore '%s' sconosciuto; ritorno pesi uguali", name)
    except Exception:  # pragma: no cover - defensive fallback
        LOG.exception("Generatore %s fallito; ritorno a pesi uguali", name)
    # In caso di errore restituiamo una allocazione uniforme per preservare la pipeline
    return np.full_like(mu_vec, 1.0 / mu_vec.size)


def run_optimization_pipeline(
    *,
    artifacts_root: Path | None = None,
    params_path: Path | str = Path("configs") / "params.yml",
    thresholds_path: Path | str = Path("configs") / "thresholds.yml",
    config_paths: Sequence[Path | str] | None = None,
    audit_dir: Path | str | None = None,
    seed_path: Path | str | None = None,
    generators: Sequence[str] = ("A", "B", "C", "D"),
    use_meta: bool = True,
) -> OptimizePipelineResult:
    """Esegue la pipeline di ottimizzazione e persiste le allocazioni.

    La funzione coordina i generatori, l'eventuale meta-blending e il logging
    di audit emettendo messaggi descrittivi per ogni fase rilevante.
    """

    artifacts_root = Path(artifacts_root) if artifacts_root is not None else None
    LOG.info(
        "Avvio della pipeline di ottimizzazione con root=%s",
        artifacts_root or "<default>",
    )
    # Carichiamo gli artefatti prodotti dalle pipeline precedenti per garantire coerenza
    mu_post, sigma = _load_mu_sigma(artifacts_root)
    factors = _load_factors(artifacts_root)
    params, thresholds = _load_configs(Path(params_path), Path(thresholds_path))

    mu_vec = mu_post.to_numpy(dtype=float)
    scenarios = factors.to_numpy(dtype=float)
    n_assets = mu_vec.size

    execution = thresholds.get("execution", {}) if isinstance(thresholds, dict) else {}
    tau = thresholds.get("tau", {}) if isinstance(thresholds, dict) else {}

    household = params.get("household", {}) if isinstance(params, dict) else {}
    cvar_cap = float(household.get("cvar_cap_1m", 0.10))
    edar_cap = float(household.get("edar_cap_3y", 0.20))

    # Determiniamo i cluster di asset per gli algoritmi che sfruttano la struttura ERC
    clusters = _cluster_indices(n_assets)
    constraints = {
        "scenario_returns": scenarios,
        "edar_scenarios": scenarios,
        "cvar_cap": cvar_cap,
        "cvar_alpha": 0.05,
        "edar_cap": edar_cap,
        "edar_alpha": 0.8,
        "gross_leverage_cap": float(execution.get("gross_leverage_cap", 1.75)),
        "turnover_cap": float(execution.get("turnover_cap", 0.40)),
        "clusters": clusters,
        "erc_tol": float(tau.get("rc_tol", 0.02)),
        "dro_rho": 0.05,
        "risk_aversion": 1e-4,
    }

    generator_paths: dict[str, Path] = {}
    generator_weights: list[np.ndarray] = []
    generator_names: list[str] = []

    if not generators:
        raise ValueError("È necessario richiedere almeno un generatore")

    # Eseguiamo ogni generatore richiesto garantendo che i pesi siano normalizzati
    for name in generators:
        weights = _run_generator(name, mu_vec, sigma, constraints)
        weights = np.asarray(weights, dtype=float)
        if weights.shape[0] != n_assets:
            weights = np.full(n_assets, 1.0 / n_assets)
            LOG.warning(
                "Il generatore %s ha prodotto %s pesi; attesi %s. Uso pesi uguali.",
                name,
                weights.shape[0],
                n_assets,
            )
        weights = np.clip(weights, 0.0, None)
        total = np.sum(weights)
        if total > 0:
            weights /= total
        generator_weights.append(weights)
        generator_names.append(name)
        path = artifact_path("weights", f"generator_{name}.csv", root=artifacts_root)
        pd.Series(weights, index=mu_post.index, name="weight").to_csv(path)
        generator_paths[name] = path
        LOG.info("Pesi del generatore %s scritti su %s", name, path)

    # Aggregazione deterministica dei risultati dei generatori per eventuale meta-blending
    weights_matrix = np.vstack(generator_weights)
    returns_matrix = scenarios @ weights_matrix.T

    meta_weights_path: Path | None = None
    allocation = generator_weights[0]
    if use_meta and len(generator_weights) >= 2:
        penalty_te = float(execution.get("TE_max_factor", 0.02))
        n_meta = min(3, len(generator_weights))
        returns_subset = returns_matrix[:, :n_meta]
        weights_subset = weights_matrix[:n_meta]
        names_subset = generator_names[:n_meta]
        meta = fit_meta_weights(
            returns_subset,
            sigma,
            j_max=n_meta,
            penalty_to=0.1,
            penalty_te=penalty_te,
            baseline_idx=0,
        )
        meta = np.asarray(meta, dtype=float)
        meta_weights_path = artifact_path("weights", "meta_weights.csv", root=artifacts_root)
        pd.Series(meta, index=names_subset, name="alpha").to_csv(meta_weights_path)
        allocation = (meta @ weights_subset).astype(float)
        LOG.info(
            "Meta-learner ha combinato %s generatori (penalty_te=%s)",
            len(names_subset),
            penalty_te,
        )
        allocation = np.clip(allocation, 0.0, None)
        total = allocation.sum()
        if total > 0:
            allocation /= total
    else:
        if not use_meta:
            LOG.info("Meta blending disattivato dall'utente")
        else:
            LOG.info("Meta blending saltato: generatori insufficienti")

    allocation_series = pd.Series(allocation, index=mu_post.index, name="weight")
    allocation_path = artifact_path("weights", "factor_allocation.csv", root=artifacts_root)
    allocation_series.to_csv(allocation_path)
    LOG.info("Allocazione finale salvata in %s", allocation_path)

    # Calcoliamo contributi di rischio e diagnostica per facilitare il debug successivo
    rc = risk_contributions(allocation, sigma)
    diagnostics = pd.DataFrame(
        {"factor": mu_post.index, "risk_contribution": rc, "weight": allocation}
    )
    diagnostics_path = artifact_path("weights", "allocation_diagnostics.csv", root=artifacts_root)
    diagnostics.to_csv(diagnostics_path, index=False)
    LOG.debug("Diagnostica dei contributi di rischio scritta in %s", diagnostics_path)

    if config_paths is None:
        config_paths = (
            Path("configs") / "params.yml",
            Path("configs") / "thresholds.yml",
            Path("configs") / "goals.yml",
        )
    audit_summary = run_audit_snapshot(
        seed_path=seed_path or DEFAULT_SEED_PATH,
        config_paths=config_paths,
        audit_dir=audit_dir,
        note="pipeline ottimizzazione",
        checksums={
            "allocation": str(allocation_path),
            "diagnostics": str(diagnostics_path),
            **{f"gen_{k}": str(v) for k, v in generator_paths.items()},
        },
    )
    LOG.debug("Artefatti di audit: %s", audit_summary)

    return OptimizePipelineResult(
        allocation_path=allocation_path,
        generator_paths=generator_paths,
        meta_weights_path=meta_weights_path,
        diagnostics_path=diagnostics_path,
    )
