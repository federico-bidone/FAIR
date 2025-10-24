from __future__ import annotations

from pathlib import Path

import pandas as pd

from fair3.engine.etl.make_tr_panel import PanelBuilder


def test_compute_returns_handles_duplicate_index(tmp_path: Path) -> None:
    dates = pd.to_datetime(["2024-01-02", "2024-01-02", "2024-01-03"])
    prices = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["USD", "USD", "USD"],
            "price": [1.10, 1.10, 1.11],
        }
    )
    prices = prices.set_index(["symbol", "date"]).sort_index()

    builder = PanelBuilder(
        raw_root=tmp_path / "data" / "raw",
        clean_root=tmp_path / "data" / "clean",
        audit_root=tmp_path / "audit",
    )
    ret = builder._compute_returns(prices)
    assert ret.index.is_unique
