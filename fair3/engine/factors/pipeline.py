from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.reporting.audit import run_audit_snapshot
from fair3.engine.utils.io import artifact_path, ensure_dir, write_json
from fair3.engine.utils.rand import DEFAULT_SEED_PATH

from .core import FactorLibrary
from .orthogonality import enforce_orthogonality
from .validation import validate_factor_set


@dataclass(slots=True)
class FactorPipelineResult:
    """Bundle describing generated factor artefacts."""

    factors_path: Path
    orthogonal_path: Path
    metadata_path: Path
    validation_path: Path | None


def _multiindex_to_datetime(index: pd.MultiIndex) -> pd.MultiIndex:
    if not isinstance(index, pd.MultiIndex) or index.nlevels != 2:
        raise TypeError("expected MultiIndex with (date, symbol)")
    dates = pd.to_datetime(index.get_level_values(0))
    symbols = index.get_level_values(1)
    return pd.MultiIndex.from_arrays([dates, symbols], names=index.names)


def _load_panel(clean_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None]:
    returns = pd.read_parquet(clean_root / "returns.parquet")
    features = pd.read_parquet(clean_root / "features.parquet")
    returns.index = _multiindex_to_datetime(returns.index)
    features.index = _multiindex_to_datetime(features.index)
    macro_path = clean_root / "macro.parquet"
    macro = None
    if macro_path.exists():
        macro = pd.read_parquet(macro_path)
        if not isinstance(macro.index, pd.DatetimeIndex):
            macro.index = pd.to_datetime(macro.index)
    return returns, features, macro


def _write_metadata(
    library: FactorLibrary,
    merged: dict[str, list[str]],
    loadings: pd.DataFrame,
    condition_number: float,
    *,
    artifacts_root: Path | None,
) -> Path:
    payload = {
        "definitions": [asdict(defn) for defn in library.definitions],
        "merged": merged,
        "condition_number": condition_number,
        "loadings_columns": list(loadings.columns),
        "loadings_index": list(loadings.index),
    }
    meta_path = artifact_path("factors", "metadata.json", root=artifacts_root)
    write_json(payload, meta_path)
    loadings_path = artifact_path("factors", "orth_loadings.csv", root=artifacts_root)
    loadings.to_csv(loadings_path, index=True)
    return meta_path


def _write_validation(
    factors: pd.DataFrame,
    returns: pd.DataFrame,
    *,
    oos_splits: int,
    embargo: int,
    seed: int,
    artifacts_root: Path | None,
) -> Path | None:
    try:
        asset_panel = returns["ret"].unstack(level="symbol").sort_index()
    except KeyError:  # pragma: no cover - defensive
        asset_panel = returns.sort_index().unstack(level="symbol")
    asset_panel.index = pd.to_datetime(asset_panel.index)
    results = validate_factor_set(
        factors,
        asset_panel,
        n_splits=oos_splits,
        embargo=embargo,
        seed=seed,
    )
    if not results:
        return None
    frame = pd.DataFrame([asdict(res) for res in results])
    validation_path = artifact_path("factors", "validation.csv", root=artifacts_root)
    frame.to_csv(validation_path, index=False)
    return validation_path


def run_factor_pipeline(
    *,
    clean_root: Path | str = Path("data") / "clean",
    artifacts_root: Path | None = None,
    config_paths: Sequence[Path | str] | None = None,
    audit_dir: Path | str | None = None,
    seed_path: Path | str | None = None,
    seed: int = 0,
    validate: bool = True,
    oos_splits: int = 5,
    embargo: int = 5,
) -> FactorPipelineResult:
    """Compute factor premia, validation diagnostics, and metadata."""

    clean_root = Path(clean_root)
    artifacts_root = Path(artifacts_root) if artifacts_root is not None else None
    returns, features, macro = _load_panel(clean_root)

    library = FactorLibrary(returns, features, macro=macro, seed=seed)
    factors = library.compute()
    factors.index = pd.to_datetime(factors.index)
    factors_path = artifact_path("factors", "factors.parquet", root=artifacts_root)
    factors.to_parquet(factors_path)

    try:
        ortho = enforce_orthogonality(factors, corr_threshold=0.85, cond_threshold=50.0)
        orth_factors = ortho.factors
        merged = ortho.merged
        loadings = ortho.loadings
        cond_number = ortho.condition_number
    except np.linalg.LinAlgError:
        orth_factors = factors
        merged = {name: [name] for name in factors.columns}
        identity = np.eye(len(factors.columns))
        loadings = pd.DataFrame(identity, index=factors.columns, columns=factors.columns)
        cond_number = 1.0

    orthogonal_path = artifact_path("factors", "factors_orthogonal.parquet", root=artifacts_root)
    orth_factors.to_parquet(orthogonal_path)

    metadata_path = _write_metadata(
        library,
        merged,
        loadings,
        cond_number,
        artifacts_root=artifacts_root,
    )

    validation_path: Path | None = None
    if validate:
        validation_path = _write_validation(
            orth_factors,
            returns,
            oos_splits=oos_splits,
            embargo=embargo,
            seed=seed,
            artifacts_root=artifacts_root,
        )

    if config_paths is None:
        config_paths = (
            Path("configs") / "params.yml",
            Path("configs") / "thresholds.yml",
            Path("configs") / "goals.yml",
        )
    ensure_dir(artifact_path("factors", create=True, root=artifacts_root).parent)
    run_audit_snapshot(
        seed_path=seed_path or DEFAULT_SEED_PATH,
        config_paths=config_paths,
        audit_dir=audit_dir,
        note="factor pipeline",
        checksums={
            "factors": str(factors_path),
            "factors_orthogonal": str(orthogonal_path),
            "metadata": str(metadata_path),
        },
    )

    return FactorPipelineResult(
        factors_path=factors_path,
        orthogonal_path=orthogonal_path,
        metadata_path=metadata_path,
        validation_path=validation_path,
    )
