"""Modulo di convenienza che espone la pipeline dell'universo investibile."""

from .models import UniversePipelineResult
from .pipeline import run_universe_pipeline

__all__ = ["UniversePipelineResult", "run_universe_pipeline"]
