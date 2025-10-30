from __future__ import annotations

import pytest

try:
    from hypothesis import given
    from hypothesis import strategies as st
except ModuleNotFoundError:  # pragma: no cover - dipendenza opzionale
    pytest.skip("Richiede la libreria hypothesis", allow_module_level=True)

from fair3.engine.utils import sha256_file


@given(data=st.binary())
def test_sha256_stable(tmp_path_factory: pytest.TempPathFactory, data: bytes) -> None:
    path = tmp_path_factory.mktemp("blob") / "blob.bin"
    path.write_bytes(data)
    assert sha256_file(path) == sha256_file(path)
