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

    panel = pd.read_parquet(artifacts.panel_path)
    pivot = panel.pivot_table(index=["date", "symbol"], columns="field", values="value")
    pivot.index = pd.MultiIndex.from_tuples(
        [
            (
                pd.to_datetime(idx[0]).tz_convert("Europe/Rome").tz_localize(None),
                idx[1],
            )
            for idx in pivot.index
        ],
        names=["date", "symbol"],
    )

    returns = pivot[["ret", "log_ret", "log_ret_estimation"]]
    features = pivot[["lag_ma_5", "lag_ma_21", "lag_vol_21"]]

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
