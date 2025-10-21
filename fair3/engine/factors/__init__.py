"""Factor generation, validation, and orthogonality utilities."""

from .core import FactorDefinition, FactorLibrary, compute_macro_factors
from .orthogonality import OrthogonalizationResult, enforce_orthogonality, merge_correlated_factors
from .pipeline import FactorPipelineResult, run_factor_pipeline
from .validation import (
    FactorValidationResult,
    cross_purged_splits,
    deflated_sharpe_ratio,
    fdr_bh,
    validate_factor_set,
    white_reality_check_pvalue,
)

__all__ = [
    "FactorDefinition",
    "FactorLibrary",
    "compute_macro_factors",
    "OrthogonalizationResult",
    "enforce_orthogonality",
    "merge_correlated_factors",
    "FactorValidationResult",
    "cross_purged_splits",
    "deflated_sharpe_ratio",
    "fdr_bh",
    "validate_factor_set",
    "white_reality_check_pvalue",
    "FactorPipelineResult",
    "run_factor_pipeline",
]
