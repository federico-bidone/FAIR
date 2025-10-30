import numpy as np
import pytest

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.utils import project_to_psd


@settings(max_examples=20, deadline=None)
@given(st.integers(min_value=2, max_value=15))
def test_project_to_psd_eigenvalues_non_negative(dim: int) -> None:
    rng = np.random.default_rng(42)
    matrix = rng.standard_normal(size=(dim, dim))
    matrix = 0.5 * (matrix + matrix.T)
    projected = project_to_psd(matrix)
    eigs = np.linalg.eigvalsh(projected)
    assert eigs.min() >= -1e-10


@given(st.integers(min_value=2, max_value=10))
def test_project_to_psd_idempotent_for_psd(dim: int) -> None:
    rng = np.random.default_rng(123)
    matrix = rng.standard_normal(size=(dim, dim))
    psd = project_to_psd(matrix)
    psd_again = project_to_psd(psd)
    diff = np.linalg.norm(psd - psd_again, ord="fro")
    assert diff <= 5e-6
