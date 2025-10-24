from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.robustness import (
    RobustnessConfig,
    block_bootstrap_metrics,
    replay_shocks,
    run_robustness_lab,
)


def test_block_bootstrap_metrics_deterministic() -> None:
    returns = pd.Series(np.full(120, 0.002, dtype="float64"))
    metrics, gates = block_bootstrap_metrics(
        returns,
        block_size=12,
        draws=32,
        cagr_target=-0.01,
        max_drawdown_threshold=-0.50,
        seed=123,
    )
    assert len(metrics) == 32
    assert np.isclose(metrics["max_drawdown"].std(ddof=0), 0.0)
    assert gates.exceedance_probability == 0.0
    assert gates.passes()


def test_replay_shocks_sorted_by_drawdown() -> None:
    returns = pd.Series(np.random.default_rng(0).normal(0.001, 0.01, size=256))
    scenarios = replay_shocks(returns, periods_per_year=252)
    assert list(scenarios.columns) == ["scenario", "length", "max_drawdown", "cagr"]
    # Ensure scenarios are sorted from worst drawdown upward
    drawdowns = scenarios["max_drawdown"].to_numpy()
    assert np.all(drawdowns[:-1] <= drawdowns[1:])


def test_run_robustness_lab_generates_artifacts(tmp_path: Path) -> None:
    returns = pd.Series(np.linspace(-0.01, 0.02, num=180))
    config = RobustnessConfig(draws=32, block_size=20, output_dir=tmp_path)

    def runner(flags: dict[str, bool], seed: int | None = None) -> dict[str, float]:
        scale = 1.0 if flags.get("bl_fallback", True) else 0.8
        rng = np.random.default_rng(seed)
        simulated = rng.normal(0.005 * scale, 0.01, size=64)
        sharpe = float(np.mean(simulated) / np.std(simulated, ddof=0))
        return {"sharpe": sharpe, "max_drawdown": float(np.min(simulated.cumsum()))}

    artifacts, gates = run_robustness_lab(
        returns,
        config=config,
        seed=21,
        ablation_runner=runner,
    )
    for path in (
        artifacts.bootstrap_csv,
        artifacts.scenarios_csv,
        artifacts.summary_json,
        artifacts.report_pdf,
        artifacts.ablation_csv,
    ):
        assert path is not None and path.exists()

    payload = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))
    assert set(payload) == {
        "max_drawdown_threshold",
        "cagr_target",
        "exceedance_probability",
        "cagr_lower_bound",
        "alpha",
        "passes",
    }
    assert isinstance(gates.passes(), bool)
