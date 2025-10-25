"""Laboratorio di robustezza per FAIR-III con API commentate in italiano."""

from .ablation import DEFAULT_FEATURES, AblationOutcome, run_ablation_study
from .bootstrap import RobustnessGates, block_bootstrap_metrics
from .lab import RobustnessArtifacts, RobustnessConfig, run_robustness_lab
from .scenarios import ShockScenario, default_shock_scenarios, replay_shocks

__all__ = [
    "DEFAULT_FEATURES",
    "AblationOutcome",
    "run_ablation_study",
    "RobustnessGates",
    "block_bootstrap_metrics",
    "RobustnessArtifacts",
    "RobustnessConfig",
    "run_robustness_lab",
    "ShockScenario",
    "default_shock_scenarios",
    "replay_shocks",
]
