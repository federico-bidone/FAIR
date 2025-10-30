from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.factors.orthogonality import condition_number, enforce_orthogonality


@given(
    n_rows=st.integers(min_value=20, max_value=60),
    n_cols=st.integers(min_value=3, max_value=6),
)
@settings(max_examples=25)
def test_orthogonalisation_does_not_increase_condition_number(n_rows: int, n_cols: int) -> None:
    rng = np.random.default_rng(n_rows * 97 + n_cols)
    data = rng.normal(size=(n_rows, n_cols))
    dates = pd.date_range("2022-01-01", periods=n_rows, freq="B")
    frame = pd.DataFrame(data, index=dates, columns=[f"f{i}" for i in range(n_cols)])
    original = condition_number(frame)
    result = enforce_orthogonality(frame, corr_threshold=0.85, cond_threshold=20)
    assert result.condition_number <= original + 1e-6
