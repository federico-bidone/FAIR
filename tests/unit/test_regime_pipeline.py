from pathlib import Path

import hashlib
import numpy as np
import pandas as pd
import pytest
import yaml

from fair3.engine.regime import run_regime_pipeline
from fair3.engine.utils import io as io_utils


def _write_clean_panel(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    idx = pd.date_range("2020-01-01", periods=90, freq="B")
    symbols = ["EQT", "BND", "ALT"]
    index = pd.MultiIndex.from_product([idx, symbols], names=["date", "symbol"])
    rng = np.random.default_rng(123)
    returns = pd.DataFrame(
        {
            "log_ret": rng.normal(0.0005, 0.01, size=len(index)),
            "ret": rng.normal(0.0005, 0.01, size=len(index)),
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "lag_vol_21": rng.uniform(0.01, 0.05, size=len(index)),
            "inflation_yoy": rng.normal(2.0, 0.1, size=len(index)),
            "pmi": rng.normal(51.0, 1.0, size=len(index)),
            "real_rate": rng.normal(-0.005, 0.002, size=len(index)),
        },
        index=index,
    )
    panel_frames: list[pd.DataFrame] = []
    for field_name in returns.columns:
        part = returns[field_name].rename("value").reset_index()
        part["field"] = field_name
        panel_frames.append(part)
    for field_name in features.columns:
        part = features[field_name].rename("value").reset_index()
        part["field"] = field_name
        panel_frames.append(part)
    panel = pd.concat(panel_frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"]).dt.tz_localize("Europe/Rome").dt.tz_convert("UTC")
    panel["currency"] = "EUR"
    panel["source"] = "synthetic"
    panel["license"] = "internal"
    panel["tz"] = "Europe/Rome"
    panel["quality_flag"] = "clean"
    panel["revision_tag"] = "qa_regime"
    panel["checksum"] = panel.apply(
        lambda row: hashlib.sha256(
            f"{row['symbol']}|{row['field']}|{row['date'].isoformat()}|{float(row['value']):.12f}".encode(
                "utf-8"
            )
        ).hexdigest(),
        axis=1,
    )
    panel["pit_flag"] = 1
    panel.to_parquet(root / "asset_panel.parquet")


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
            "weights": {"hmm": 0.5, "volatility": 0.3, "macro": 0.2},
            "volatility": {"window": 63, "min_duration": 5, "smoothing": 5},
            "macro": {
                "inflation_weight": 0.4,
                "pmi_weight": 0.35,
                "real_rate_weight": 0.25,
                "pmi_threshold": 50.0,
                "real_rate_threshold": 0.0,
                "smoothing": 3,
            },
        },
        "drift": {"weight_tol": 0.02, "rc_tol": 0.02},
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    return path


def test_run_regime_pipeline_writes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean_root = tmp_path / "clean"
    _write_clean_panel(clean_root)
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setattr(io_utils, "ARTIFACTS_ROOT", artifacts_root)
    thresholds_path = _write_thresholds(tmp_path / "thresholds.yml")

    result = run_regime_pipeline(
        clean_root=clean_root,
        thresholds_path=thresholds_path,
        output_dir=artifacts_root,
        seed=5,
        dry_run=True,
        trace=True,
    )

    assert result.probabilities_path.exists()
    frame = pd.read_csv(result.probabilities_path, parse_dates=["date"])
    assert {"p_crisis", "regime_flag"}.issubset(set(frame.columns))
    assert frame["regime_flag"].isin({0.0, 1.0}).all()
