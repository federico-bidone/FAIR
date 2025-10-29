"""Quality assurance orchestration helpers for FAIR-III.

This package exposes typed entrypoints that allow callers to launch the
deterministic QA demo outside of the CLI while keeping full audit context.
"""

from fair3.engine.qa.pipeline import DemoQAConfig, DemoQAResult, run_demo_qa

__all__ = ["DemoQAConfig", "DemoQAResult", "run_demo_qa"]
