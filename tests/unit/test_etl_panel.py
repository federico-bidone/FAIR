from __future__ import annotations

from pathlib import Path

import pandas as pd

from fair3.engine.etl.make_tr_panel import TRPanelBuilder


def _write_raw_series(path: Path, symbol: str, start: str, values: list[float]) -> None:
    dates = pd.date_range(start=start, periods=len(values), freq="B")
    frame = pd.DataFrame({"date": dates, "value": values, "symbol": symbol})
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def test_tr_panel_builder_creates_artifacts(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    clean_root = tmp_path / "clean"
    audit_root = tmp_path / "audit"

    _write_raw_series(
        raw_root / "ecb" / "a.csv",
        "AAA",
        "2020-01-01",
        [100, 101, 103, 104, 105, 104],
    )
    _write_raw_series(
        raw_root / "fred" / "b.csv",
        "BBB",
        "2020-01-01",
        [50, 51, 52, 52.5, 53, 54],
    )

    builder = TRPanelBuilder(
        raw_root=raw_root,
        clean_root=clean_root,
        audit_root=audit_root,
        base_currency="EUR",
    )
    artifacts = builder.build(seed=0)

    prices = pd.read_parquet(artifacts.prices_path)
    returns = pd.read_parquet(artifacts.returns_path)
    features = pd.read_parquet(artifacts.features_path)
    qa = pd.read_csv(artifacts.qa_path)

    expected_price_cols = {
        "price",
        "currency",
        "currency_original",
        "fx_rate",
        "source",
    }
    assert {col for col in prices.columns} >= expected_price_cols
    assert set(returns.columns) == {"ret", "log_ret", "log_ret_estimation"}
    assert set(features.columns) == {"lag_ma_5", "lag_ma_21", "lag_vol_21"}
    assert set(qa.columns) == {
        "symbol",
        "source",
        "currency",
        "start",
        "end",
        "rows",
        "nulls",
        "outliers",
    }
    assert len(prices) == len(returns) == len(features)
    assert artifacts.rows == len(prices)
    assert len(artifacts.symbols) == 2
