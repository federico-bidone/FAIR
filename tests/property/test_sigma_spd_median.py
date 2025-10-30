"""Property-based checks for the SPD median covariance estimator."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.estimates.sigma import sigma_spd_median


@st.composite
def spd_covariance_frames(draw: st.DrawFn) -> list[pd.DataFrame]:
    dim = draw(st.integers(min_value=2, max_value=4))
    count = draw(st.integers(min_value=2, max_value=5))
    columns = [f"asset_{i}" for i in range(dim)]
    frames: list[pd.DataFrame] = []
    for _ in range(count):
        seed = draw(st.integers(min_value=0, max_value=2**16 - 1))
        rng = np.random.default_rng(seed)
        matrix = rng.normal(size=(dim, dim))
        cov = matrix @ matrix.T + np.eye(dim) * 0.5
        frames.append(pd.DataFrame(cov, index=columns, columns=columns))
    return frames


@settings(deadline=None, max_examples=40)
@given(spd_covariance_frames())
def test_sigma_spd_median_returns_psd(frames: list[pd.DataFrame]) -> None:
    result = sigma_spd_median(frames, max_iter=60, tol=1e-6)
    eigenvalues = np.linalg.eigvalsh(result.to_numpy())
    assert eigenvalues.min() >= -1e-8


@settings(deadline=None, max_examples=30)
@given(spd_covariance_frames())
def test_sigma_spd_median_invariant_to_order(frames: list[pd.DataFrame]) -> None:
    first = sigma_spd_median(frames, max_iter=60, tol=1e-6)
    reversed_frames = list(reversed(frames))
    second = sigma_spd_median(reversed_frames, max_iter=60, tol=1e-6)
    diff = np.linalg.norm(first.to_numpy() - second.to_numpy(), ord="fro")
    assert diff <= 1e-5
