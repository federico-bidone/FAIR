"""Allocation engines for FAIR-III."""

from .constraints import erc_cluster_violation
from .erc import balance_clusters, risk_contributions
from .gen_a import generator_A
from .gen_b_hrp import generator_B_hrp
from .gen_c_dro import generator_C_dro_closed
from .gen_d_cvar_erc import generator_D_cvar_erc
from .meta import fit_meta_weights
from .objectives import dro_penalty, sharpe_objective
from .pipeline import OptimizePipelineResult, run_optimization_pipeline

__all__ = [
    "balance_clusters",
    "dro_penalty",
    "erc_cluster_violation",
    "fit_meta_weights",
    "generator_A",
    "generator_B_hrp",
    "generator_C_dro_closed",
    "generator_D_cvar_erc",
    "risk_contributions",
    "sharpe_objective",
    "OptimizePipelineResult",
    "run_optimization_pipeline",
]
