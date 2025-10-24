from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest.ecb import ECBFetcher
from fair3.engine.ingest.registry import run_ingest

ECB_CSV = """TIME_PERIOD,OBS_VALUE
2024-01-02,1.1020
2024-01-03,1.0955
"""


@pytest.mark.usefixtures("tmp_path")
def test_run_ingest_ecb_writes_raw_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Isola directory di lavoro per scrivere in data/raw/ecb/*
    monkeypatch.chdir(tmp_path)  # cambia CWD → data/ verrà creata qui

    # Mock download + limita i simboli di default ad uno
    monkeypatch.setattr(ECBFetcher, "_download", lambda self, url, session=None: ECB_CSV)
    monkeypatch.setattr(ECBFetcher, "DEFAULT_SYMBOLS", ("USD",))

    out = run_ingest("ecb", symbols=None, start=pd.Timestamp("2024-01-01"))
    assert out is not None
    assert set(out.data.columns) == {"date", "value", "symbol"}
    assert out.data["value"].iloc[0] == pytest.approx(1.102)
    # verify ritorno minimale e side-effect su FS
    raw_dir = Path("data") / "raw" / "ecb"
    assert raw_dir.exists(), f"Missing {raw_dir}"
    csvs = list(raw_dir.glob("*.csv"))
    assert len(csvs) >= 1, "No CSV produced in data/raw/ecb"
    # sanity sul contenuto
    content = csvs[0].read_text()
    assert "2024-01-02" in content and "value" in content
