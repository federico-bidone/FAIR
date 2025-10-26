"""Pipeline di stima dei fattori con docstring e commenti in italiano."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.reporting.audit import run_audit_snapshot
from fair3.engine.utils.io import ARTIFACTS_ROOT, artifact_path, ensure_dir, read_yaml
from fair3.engine.utils.logging import get_stream_logger
from fair3.engine.utils.rand import DEFAULT_SEED_PATH

from .bl import blend_mu, reverse_opt_mu_eq
from .drift import frobenius_relative_drift, max_corr_drift
from .mu import estimate_mu_ensemble
from .sigma import (
    ewma_regime,
    factor_shrink,
    graphical_lasso_bic,
    ledoit_wolf,
    median_of_covariances,
)


LOG = get_stream_logger(__name__)


@dataclass(slots=True)
class EstimatePipelineResult:
    """Artefatti generati dalla pipeline di stima."""

    mu_post_path: Path
    mu_star_path: Path
    mu_eq_path: Path
    sigma_path: Path
    blend_log_path: Path
    drift_log_path: Path | None


def _load_factors(artifacts_root: Path | None) -> pd.DataFrame:
    """Restituisce il pannello di fattori ortogonali necessario alla stima."""

    path = artifact_path("factors", "factors_orthogonal.parquet", root=artifacts_root)
    if not path.exists():
        raise FileNotFoundError(
            "Artefatto dei fattori mancante. Eseguire `fair3 factors` prima delle stime."
        )
    LOG.debug("Carico fattori da %s", path)
    factors = pd.read_parquet(path)
    if not isinstance(factors.index, pd.DatetimeIndex):
        factors.index = pd.to_datetime(factors.index)
    return factors


def _load_thresholds(config_path: Path) -> dict:
    """Carica e valida la mappatura delle soglie di configurazione."""

    data = read_yaml(config_path)
    if not isinstance(data, dict):
        LOG.warning(
            "La configurazione delle soglie in %s non è una mappatura; uso {} di default",
            config_path,
        )
        return {}
    LOG.debug("Soglie caricate da %s", config_path)
    return data


def _to_correlation(matrix: np.ndarray) -> np.ndarray:
    """Converte ``matrix`` in una matrice di correlazione gestendo le diagonali."""

    diag = np.diag(matrix)
    scale = np.sqrt(np.clip(diag, 1e-12, None))
    denom = np.outer(scale, scale)
    # Evitiamo divisioni per zero quando la varianza è nulla
    with np.errstate(divide="ignore", invalid="ignore"):
        corr = np.divide(matrix, denom, out=np.zeros_like(matrix), where=denom > 0)
    np.fill_diagonal(corr, 1.0)
    return corr


def _write_series(series: pd.Series, *, name: str, artifacts_root: Path | None) -> Path:
    """Persiste una serie nella directory delle stime e ne restituisce il percorso."""

    frame = series.rename(name).to_frame()
    path = artifact_path("estimates", f"{name}.csv", root=artifacts_root)
    frame.to_csv(path)
    LOG.debug("Scritta la serie %s su %s", name, path)
    return path


def _append_drift_log(path: Path, frob: float, corr: float) -> Path:
    """Aggiunge un nuovo record di drift a ``path`` e lo restituisce."""

    columns = ["frobenius_relative", "max_corr_drift"]
    record = pd.DataFrame([[frob, corr]], columns=columns)
    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, record], ignore_index=True)
    else:
        combined = record
    combined.to_csv(path, index=False)
    LOG.debug("Registro del drift aggiornato in %s", path)
    return path


def run_estimate_pipeline(
    *,
    artifacts_root: Path | None = None,
    thresholds_path: Path | str = Path("configs") / "thresholds.yml",
    config_paths: Sequence[Path | str] | None = None,
    audit_dir: Path | str | None = None,
    seed_path: Path | str | None = None,
    cv_splits: int = 5,
    seed: int = 0,
) -> EstimatePipelineResult:
    """Stima rendimenti attesi e matrici di covarianza di consenso.

    La routine coordina l'ensemble deterministico, gli shrinkage, il blending
    Black–Litterman e le diagnostiche di drift emettendo log strutturati utili
    al debug.
    """

    artifacts_root = Path(artifacts_root) if artifacts_root is not None else None
    LOG.info("Avvio della pipeline di stima con root=%s", artifacts_root or "<default>")
    factors = _load_factors(artifacts_root)
    if factors.empty:
        raise ValueError("Il pannello dei fattori è vuoto")

    # Puliamo il pannello per evitare valori mancanti che inquinerebbero le stime
    factors = factors.dropna(how="all").fillna(0.0)
    thresholds = _load_thresholds(Path(thresholds_path))
    tau = thresholds.get("tau", {}) if isinstance(thresholds, dict) else {}
    tau_ir = float(tau.get("IR_view", 0.15))
    vol_target = float(thresholds.get("vol_target_annual", 0.11))

    LOG.debug(
        "Stimo l'ensemble di mu con %s fattori e %s osservazioni",
        factors.shape[1],
        factors.shape[0],
    )
    mu_star = estimate_mu_ensemble(
        factors,
        pd.DataFrame(index=factors.index),
        cv_splits,
        seed,
    )
    mu_star = mu_star.reindex(factors.columns).fillna(0.0)

    sample = factors.to_numpy(dtype=float)
    cov_inputs = pd.DataFrame(sample, index=factors.index, columns=factors.columns)
    cov_lw = ledoit_wolf(cov_inputs)
    try:
        cov_gl = graphical_lasso_bic(cov_inputs)
    except Exception:
        LOG.exception("Graphical lasso fallito; ritorno alla stima Ledoit-Wolf")
        cov_gl = cov_lw
    try:
        cov_factor = factor_shrink(cov_inputs)
    except Exception:
        LOG.exception("Factor shrink fallito; ritorno alla stima Ledoit-Wolf")
        cov_factor = cov_lw
    # Combiniamo le diverse stime di covarianza per stabilizzare il risultato finale
    sigma_median = median_of_covariances([cov_lw, cov_gl, cov_factor])
    sigma_df = pd.DataFrame(sigma_median, index=factors.columns, columns=factors.columns)

    sigma_path = artifact_path("estimates", "sigma.npy", root=artifacts_root)
    sigma_prev: np.ndarray | None = None
    sigma_prev_df: pd.DataFrame | None = None
    if sigma_path.exists():
        sigma_prev = np.load(sigma_path)
        if sigma_prev.shape == sigma_df.shape:
            sigma_prev_df = pd.DataFrame(sigma_prev, index=factors.columns, columns=factors.columns)
    sigma_final_df = sigma_df.copy()
    if sigma_prev_df is not None:
        sigma_final_df[:] = ewma_regime(sigma_prev_df.to_numpy(), sigma_df.to_numpy(), lambda_r=0.5)
        LOG.info("Applicata la fusione EWMA rispetto alla sigma precedente")
    np.save(sigma_path, sigma_final_df.to_numpy())
    LOG.debug("Matrice sigma salvata in %s", sigma_path)

    assets = mu_star.index
    sigma_aligned_df = sigma_final_df.reindex(index=assets, columns=assets).fillna(0.0)
    sigma_matrix = sigma_aligned_df.to_numpy()
    w_mkt = pd.Series(np.full(len(assets), 1.0 / len(assets)), index=assets)
    mu_eq = reverse_opt_mu_eq(sigma_matrix, w_mkt, vol_target).reindex(mu_star.index).fillna(0.0)

    diff = (mu_star - mu_eq).to_numpy(dtype=float)
    inv_sigma = np.linalg.pinv(sigma_matrix + 1e-8 * np.eye(sigma_matrix.shape[0]))
    ir_view = float(np.sqrt(max(diff.T @ inv_sigma @ diff, 0.0)))
    blend = blend_mu(mu_eq, mu_star, ir_view, tau_ir)
    LOG.info("Blending con omega=%s (%s)", blend.omega, blend.reason)

    mu_post_path = _write_series(blend.mu_post, name="mu_post", artifacts_root=artifacts_root)
    mu_star_path = _write_series(mu_star, name="mu_star", artifacts_root=artifacts_root)
    mu_eq_path = _write_series(mu_eq, name="mu_eq", artifacts_root=artifacts_root)

    blend_log = pd.DataFrame(
        [
            {
                "omega": blend.omega,
                "reason": blend.reason,
                "ir_view": ir_view,
                "tau_ir": tau_ir,
            }
        ]
    )
    blend_log_path = artifact_path("estimates", "blend_log.csv", root=artifacts_root)
    blend_log.to_csv(blend_log_path, index=False)
    LOG.debug("Diagnostica del blend salvata in %s", blend_log_path)

    drift_log_path: Path | None = None
    if sigma_prev_df is not None:
        # Se esiste una matrice precedente calcoliamo indicatori di drift per monitorare stabilità
        prev_mat = sigma_prev_df.to_numpy()
        curr_mat = sigma_final_df.to_numpy()
        frob = frobenius_relative_drift(curr_mat, prev_mat)
        corr_prev = _to_correlation(prev_mat)
        corr_curr = _to_correlation(curr_mat)
        corr_delta = max_corr_drift(corr_curr, corr_prev) if corr_prev.size else 0.0
        drift_dir = ensure_dir(Path(artifacts_root or ARTIFACTS_ROOT) / "risk")
        drift_log_path = _append_drift_log(drift_dir / "sigma_drift_log.csv", frob, corr_delta)
        LOG.info("Drift di sigma frob=%.4f corr_delta=%.4f", frob, corr_delta)

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
        note="pipeline stima",
        checksums={
            "mu_post": str(mu_post_path),
            "mu_star": str(mu_star_path),
            "sigma": str(sigma_path),
            "blend_log": str(blend_log_path),
        },
    )
    LOG.debug("Artefatti di audit: %s", audit_summary)

    return EstimatePipelineResult(
        mu_post_path=mu_post_path,
        mu_star_path=mu_star_path,
        mu_eq_path=mu_eq_path,
        sigma_path=sigma_path,
        blend_log_path=blend_log_path,
        drift_log_path=drift_log_path,
    )
