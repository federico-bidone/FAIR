from __future__ import annotations

from pathlib import Path

import hashlib
import numpy as np
import pandas as pd
import pytest

from fair3.cli.main import main as cli_main
from fair3.engine.utils import io as io_utils
from fair3.engine.utils import rand as rand_utils


def _write_clean_panel(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2020-01-31", periods=36, freq=pd.offsets.MonthEnd())
    symbols = ["EQT", "BND", "ALT"]
    index = pd.MultiIndex.from_product([dates, symbols], names=["date", "symbol"])
    rng = np.random.default_rng(42)
    ret = rng.normal(0.01, 0.04, size=len(index))
    returns = pd.DataFrame(
        {
            "ret": ret,
            "log_ret": np.log1p(ret).clip(-0.2, 0.2),
            "log_ret_estimation": np.log1p(ret).clip(-0.2, 0.2),
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "lag_ma_5": rng.normal(0.0, 0.01, size=len(index)),
            "lag_ma_21": rng.normal(0.0, 0.01, size=len(index)),
            "lag_vol_21": rng.uniform(0.01, 0.05, size=len(index)),
        },
        index=index,
    )
    frames: list[pd.DataFrame] = []
    for field_name in returns.columns:
        part = returns[field_name].rename("value").reset_index()
        part["field"] = field_name
        frames.append(part)
    for field_name in features.columns:
        part = features[field_name].rename("value").reset_index()
        part["field"] = field_name
        frames.append(part)
    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"]).dt.tz_localize("Europe/Rome").dt.tz_convert("UTC")
    panel["currency"] = "EUR"
    panel["source"] = "synthetic"
    panel["license"] = "internal"
    panel["tz"] = "Europe/Rome"
    panel["quality_flag"] = "clean"
    panel["revision_tag"] = "cli_pipeline"
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


@pytest.fixture()
def patched_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    clean_root = tmp_path / "clean"
    _write_clean_panel(clean_root)
    artifacts_root = tmp_path / "artifacts"
    monkeypatch.setattr(io_utils, "ARTIFACTS_ROOT", artifacts_root)
    monkeypatch.setattr(rand_utils, "DEFAULT_SEED_PATH", tmp_path / "audit" / "seeds.yml")
    return clean_root


def test_cli_pipeline_end_to_end(tmp_path: Path, patched_environment: Path) -> None:
    clean_root = patched_environment
    artifacts_root = io_utils.ARTIFACTS_ROOT

    cli_main(
        [
            "factors",
            "--clean-root",
            str(clean_root),
            "--validate",
            "--artifacts-root",
            str(artifacts_root),
        ]
    )
    cli_main(
        [
            "estimate",
            "--artifacts-root",
            str(artifacts_root),
            "--sigma-engine",
            "spd_median",
        ]
    )
    cli_main(
        [
            "optimize",
            "--artifacts-root",
            str(artifacts_root),
            "--meta",
        ]
    )
    cli_main(
        [
            "map",
            "--artifacts-root",
            str(artifacts_root),
            "--clean-root",
            str(clean_root),
            "--hrp-intra",
            "--adv-cap",
            "0.05",
            "--te-factor-max",
            "0.02",
            "--tau-beta",
            "0.25",
        ]
    )

    assert (artifacts_root / "factors" / "factors.parquet").exists()
    assert (artifacts_root / "estimates" / "mu_post.csv").exists()
    assert (artifacts_root / "weights" / "factor_allocation.csv").exists()
    assert (artifacts_root / "weights" / "instrument_allocation.csv").exists()
