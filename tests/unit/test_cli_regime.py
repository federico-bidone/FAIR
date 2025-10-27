from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from fair3.cli.main import main as cli_main
from fair3.engine.utils import io as io_utils


def _seed_clean_panel(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2020-01-01", periods=90, freq="B")
    symbols = ["EQT", "BND"]
    index = pd.MultiIndex.from_product([idx, symbols], names=["date", "symbol"])
    rng = np.random.default_rng(99)
    returns = pd.DataFrame({"log_ret": rng.normal(0.0004, 0.01, len(index))}, index=index)
    features = pd.DataFrame(
        {
            "lag_vol_21": rng.uniform(0.01, 0.04, len(index)),
            "inflation_yoy": rng.normal(2.0, 0.05, len(index)),
            "pmi": rng.normal(51.0, 0.8, len(index)),
            "real_rate": rng.normal(-0.004, 0.0015, len(index)),
        },
        index=index,
    )
    returns.to_parquet(root / "returns.parquet")
    features.to_parquet(root / "features.parquet")


def _write_thresholds(path: Path) -> Path:
    payload = {
        "vol_target_annual": 0.11,
        "tau": {
            "IR_view": 0.15,
            "sigma_rel": 0.2,
            "delta_rho": 0.15,
            "beta_CI_width": 0.25,
            "rc_tol": 0.02,
        },
        "execution": {
            "turnover_cap": 0.4,
            "gross_leverage_cap": 1.75,
            "TE_max_factor": 0.02,
            "adv_cap_ratio": 0.05,
        },
        "regime": {
            "on": 0.65,
            "off": 0.45,
            "dwell_days": 20,
            "cooldown_days": 10,
            "activate_streak": 3,
            "deactivate_streak": 3,
        },
        "drift": {"weight_tol": 0.02, "rc_tol": 0.02},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    return path


def test_cli_regime_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    clean_root = tmp_path / "clean"
    _seed_clean_panel(clean_root)
    thresholds_path = _write_thresholds(tmp_path / "thresholds.yml")
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setattr(io_utils, "ARTIFACTS_ROOT", artifacts_root)

    cli_main(
        [
            "regime",
            "--clean-root",
            str(clean_root),
            "--thresholds",
            str(thresholds_path),
            "--output-dir",
            str(artifacts_root),
            "--seed",
            "7",
            "--dry-run",
            "--trace",
        ]
    )

    captured = capsys.readouterr()
    assert "[fair3] regime" in captured.out
    assert "p_crisis=" in captured.out
    assert (artifacts_root / "regime" / "probabilities.csv").exists()
