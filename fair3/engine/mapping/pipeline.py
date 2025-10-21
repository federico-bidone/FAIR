from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.mapping import beta_ci_bootstrap, rolling_beta_ridge
from fair3.engine.mapping.hrp_intra import hrp_weights
from fair3.engine.mapping.liquidity import clip_trades_to_adv
from fair3.engine.mapping.te_budget import enforce_te_budget, tracking_error
from fair3.engine.reporting.audit import run_audit_snapshot
from fair3.engine.utils import project_to_psd
from fair3.engine.utils.io import artifact_path, read_yaml, write_json
from fair3.engine.utils.rand import DEFAULT_SEED_PATH


@dataclass(slots=True)
class MappingPipelineResult:
    beta_path: Path
    beta_ci_path: Path
    instrument_weights_path: Path
    summary_path: Path


def _load_factor_allocation(artifacts_root: Path | None) -> pd.Series:
    path = artifact_path("weights", "factor_allocation.csv", root=artifacts_root)
    if not path.exists():
        raise FileNotFoundError(
            "Missing factor allocation artefact. Run `fair3 optimize` before mapping."
        )
    return pd.read_csv(path, index_col=0).iloc[:, 0]


def _load_returns(clean_root: Path) -> pd.DataFrame:
    returns = pd.read_parquet(clean_root / "returns.parquet")
    if not isinstance(returns.index, pd.MultiIndex) or returns.index.nlevels != 2:
        raise TypeError("returns parquet must be indexed by (date, symbol)")
    dates = pd.to_datetime(returns.index.get_level_values(0))
    symbols = returns.index.get_level_values(1)
    panel = returns.copy()
    panel.index = pd.MultiIndex.from_arrays([dates, symbols], names=["date", "symbol"])
    pivot = panel["ret"].unstack(level="symbol").sort_index()
    return pivot.fillna(0.0)


def _load_factors(artifacts_root: Path | None) -> pd.DataFrame:
    path = artifact_path("factors", "factors.parquet", root=artifacts_root)
    if not path.exists():
        raise FileNotFoundError("Missing factors artefact. Run `fair3 factors` before mapping.")
    factors = pd.read_parquet(path)
    if not isinstance(factors.index, pd.DatetimeIndex):
        factors.index = pd.to_datetime(factors.index)
    return factors.fillna(0.0)


def _load_metadata(artifacts_root: Path | None) -> Mapping[str, int]:
    path = artifact_path("factors", "metadata.json", root=artifacts_root)
    if not path.exists():
        return {}
    data = read_yaml(path)
    if not isinstance(data, dict):
        return {}
    definitions = data.get("definitions", [])
    sign_map: dict[str, int] = {}
    for item in definitions:
        if isinstance(item, dict) and "name" in item and "expected_sign" in item:
            try:
                sign_map[str(item["name"])] = int(item["expected_sign"])
            except (TypeError, ValueError):  # pragma: no cover - defensive
                continue
    return sign_map


def _solve_instrument_weights(beta_matrix: np.ndarray, factor_weights: np.ndarray) -> np.ndarray:
    if beta_matrix.size == 0:
        return np.zeros_like(factor_weights)
    solution, *_ = np.linalg.lstsq(beta_matrix.T, factor_weights, rcond=None)
    solution = np.clip(solution, 0.0, None)
    total = solution.sum()
    if total > 0:
        return solution / total
    fallback = np.full(beta_matrix.shape[0], 1.0 / beta_matrix.shape[0])
    return fallback


def run_mapping_pipeline(
    *,
    artifacts_root: Path | None = None,
    clean_root: Path | str = Path("data") / "clean",
    thresholds_path: Path | str = Path("configs") / "thresholds.yml",
    config_paths: Sequence[Path | str] | None = None,
    audit_dir: Path | str | None = None,
    seed_path: Path | str | None = None,
    window: int | None = None,
    lambda_beta: float = 1.0,
    bootstrap_samples: int = 200,
    use_hrp_intra: bool = False,
    adv_cap_ratio: float | None = None,
) -> MappingPipelineResult:
    """Map factor allocations to instrument weights with TE/ADV governance."""

    artifacts_root = Path(artifacts_root) if artifacts_root is not None else None
    clean_root = Path(clean_root)
    factor_weights = _load_factor_allocation(artifacts_root)
    instrument_returns = _load_returns(clean_root)
    factors = _load_factors(artifacts_root)
    sign_map = _load_metadata(artifacts_root)

    aligned_factors = factors.reindex(instrument_returns.index).fillna(method="ffill").fillna(0.0)
    n_obs = len(aligned_factors)
    if n_obs < 2:
        raise ValueError("Not enough observations for beta mapping")
    window = window or max(12, min(60, n_obs))

    betas = rolling_beta_ridge(
        instrument_returns,
        aligned_factors,
        window=window,
        lambda_beta=lambda_beta,
        sign=sign_map,
    )
    beta_path = artifact_path("mapping", "rolling_betas.parquet", root=artifacts_root)
    betas.to_parquet(beta_path)

    beta_ci = beta_ci_bootstrap(
        instrument_returns,
        aligned_factors,
        betas,
        B=bootstrap_samples,
        alpha=0.2,
    )
    beta_ci_path = artifact_path("mapping", "beta_ci.parquet", root=artifacts_root)
    beta_ci.to_parquet(beta_ci_path)

    latest = betas.dropna(how="all")
    if latest.empty:
        raise ValueError("Rolling betas produced no finite estimates")
    row = latest.iloc[-1]
    beta_df = row.unstack(level="instrument")
    beta_matrix = beta_df.to_numpy().T
    instr_names = beta_df.columns.tolist()

    factor_vector = factor_weights.reindex(beta_df.index).fillna(0.0).to_numpy(dtype=float)
    instr_weights = _solve_instrument_weights(beta_matrix, factor_vector)

    cov_instr = np.cov(instrument_returns.to_numpy(dtype=float), rowvar=False)
    cov_instr = project_to_psd(cov_instr)

    if use_hrp_intra:
        labels = beta_df.abs().idxmax(axis=0).reindex(instr_names).fillna("cluster").tolist()
        baseline = hrp_weights(cov_instr, labels)
    else:
        baseline = np.full_like(instr_weights, 1.0 / len(instr_weights))

    thresholds = read_yaml(Path(thresholds_path))
    execution = thresholds.get("execution", {}) if isinstance(thresholds, dict) else {}
    cap = float(execution.get("TE_max_factor", 0.02))
    adjusted = enforce_te_budget(instr_weights, baseline, cov_instr, cap)

    if adv_cap_ratio is None:
        adv_cap_ratio = float(execution.get("adv_cap_ratio", 0.05))
    adv = np.ones_like(adjusted)
    prices = np.ones_like(adjusted)
    delta = adjusted - baseline
    adjusted = clip_trades_to_adv(delta, 1.0, adv, prices, adv_cap_ratio) + baseline
    adjusted = np.clip(adjusted, 0.0, None)
    total = adjusted.sum()
    if total > 0:
        adjusted /= total

    instrument_weights = pd.Series(adjusted, index=instr_names, name="weight")
    instrument_path = artifact_path("weights", "instrument_allocation.csv", root=artifacts_root)
    instrument_weights.to_csv(instrument_path)

    te_before = tracking_error(instr_weights, baseline, cov_instr)
    te_after = tracking_error(adjusted, baseline, cov_instr)
    summary = {
        "tracking_error_before": float(te_before),
        "tracking_error_after": float(te_after),
        "sum_weights": float(adjusted.sum()),
    }
    summary_path = artifact_path("mapping", "summary.json", root=artifacts_root)
    write_json(summary, summary_path)

    if config_paths is None:
        config_paths = (
            Path("configs") / "params.yml",
            Path("configs") / "thresholds.yml",
            Path("configs") / "goals.yml",
        )
    run_audit_snapshot(
        seed_path=seed_path or DEFAULT_SEED_PATH,
        config_paths=config_paths,
        audit_dir=audit_dir,
        note="mapping pipeline",
        checksums={
            "betas": str(beta_path),
            "beta_ci": str(beta_ci_path),
            "instrument_weights": str(instrument_path),
            "summary": str(summary_path),
        },
    )

    return MappingPipelineResult(
        beta_path=beta_path,
        beta_ci_path=beta_ci_path,
        instrument_weights_path=instrument_path,
        summary_path=summary_path,
    )
