from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fair3.cli.main import main as cli_main
from fair3.engine.utils import io as io_utils
from fair3.engine.utils import rand as rand_utils


def _write_clean_panel(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2020-01-31", periods=36, freq="ME")
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
    returns.to_parquet(root / "returns.parquet")
    features.to_parquet(root / "features.parquet")


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
        ]
    )

    assert (artifacts_root / "factors" / "factors.parquet").exists()
    assert (artifacts_root / "estimates" / "mu_post.csv").exists()
    assert (artifacts_root / "weights" / "factor_allocation.csv").exists()
    assert (artifacts_root / "weights" / "instrument_allocation.csv").exists()
