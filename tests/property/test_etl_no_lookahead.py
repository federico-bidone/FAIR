from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.etl.make_tr_panel import TRPanelBuilder


def _setup_raw(tmp_path: Path) -> tuple[Path, Path, Path]:
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    audit_root = tmp_path / "audit"
    dates = pd.date_range("2021-01-01", periods=15, freq="B")
    price = pd.Series(100 + np.arange(len(dates)), index=dates).astype(float)
    frame = pd.DataFrame({"date": dates, "value": price.values, "symbol": "AAA"})
    path = raw_root / "ecb" / "aaa.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    return raw_root, clean_root, audit_root


def test_features_use_only_past_observations(tmp_path: Path) -> None:
    raw_root, clean_root, audit_root = _setup_raw(tmp_path)
    builder = TRPanelBuilder(raw_root=raw_root, clean_root=clean_root, audit_root=audit_root)
    artifacts = builder.build(seed=0)

    returns = pd.read_parquet(artifacts.returns_path)
    features = pd.read_parquet(artifacts.features_path)

    # Convert index level 0 back to datetime for calculations
    returns.index = pd.MultiIndex.from_arrays(
        [
            pd.to_datetime(returns.index.get_level_values(0)),
            returns.index.get_level_values(1),
        ],
        names=returns.index.names,
    )
    features.index = pd.MultiIndex.from_arrays(
        [
            pd.to_datetime(features.index.get_level_values(0)),
            features.index.get_level_values(1),
        ],
        names=features.index.names,
    )

    grouped = returns.groupby(level="symbol")["log_ret"]
    expected_ma5 = grouped.transform(lambda s: s.shift(1).rolling(5, min_periods=1).mean())
    expected_ma21 = grouped.transform(lambda s: s.shift(1).rolling(21, min_periods=1).mean())
    rng = np.random.default_rng(0)
    vol_floor = rng.uniform(1e-8, 1e-6)
    expected_vol = grouped.transform(lambda s: s.shift(1).rolling(21, min_periods=5).std()).fillna(
        vol_floor
    )

    np.testing.assert_allclose(features["lag_ma_5"], expected_ma5, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(features["lag_ma_21"], expected_ma21, rtol=1e-9, atol=1e-9)
    np.testing.assert_allclose(features["lag_vol_21"], expected_vol, rtol=1e-9, atol=1e-9)

    # Ensure current day's return is not part of lagged averages
    merged = features.join(returns["log_ret"].rename("current"))
    same_day = merged["lag_ma_5"] - merged["current"]
    assert not np.isclose(same_day.iloc[0], merged["current"].iloc[0])
