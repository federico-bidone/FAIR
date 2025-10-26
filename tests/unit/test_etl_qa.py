"""Test italiani per il modulo QA dell'ETL."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from fair3.engine.etl import qa


def test_qa_report_to_frame_preserva_ordine() -> None:
    """I record devono essere esportati nell'ordine di inserimento."""

    report = qa.QAReport(records=[])
    report.append(
        qa.QARecord(
            symbol="AAA",
            source="alpha",
            currency="EUR",
            start=datetime(2023, 1, 1),
            end=datetime(2023, 1, 2),
            rows=10,
            nulls=0,
            outliers=1,
        )
    )
    frame = report.to_frame()
    assert list(frame.columns) == [
        "symbol",
        "source",
        "currency",
        "start",
        "end",
        "rows",
        "nulls",
        "outliers",
    ]
    assert frame.iloc[0]["symbol"] == "AAA"


def test_write_qa_log_crea_intestazione(tmp_path: Path) -> None:
    """Il log deve contenere intestazione anche in assenza di record."""

    percorso = tmp_path / "qa" / "log.csv"
    risultato = qa.write_qa_log(qa.QAReport(records=[]), percorso)
    assert risultato == percorso
    testo = percorso.read_text(encoding="utf-8")
    assert "symbol,source,currency" in testo


def test_write_qa_log_ordina_simbolo_e_sorgente(tmp_path: Path) -> None:
    """I record scritti su file devono risultare ordinati per audit."""

    report = qa.QAReport(
        records=[
            qa.QARecord(
                symbol="BBB",
                source="beta",
                currency="EUR",
                start=None,
                end=None,
                rows=1,
                nulls=0,
                outliers=0,
            ),
            qa.QARecord(
                symbol="AAA",
                source="alpha",
                currency="EUR",
                start=None,
                end=None,
                rows=2,
                nulls=1,
                outliers=0,
            ),
        ]
    )
    destinazione = tmp_path / "qa_log.csv"
    qa.write_qa_log(report, destinazione)
    frame = pd.read_csv(destinazione)
    assert frame.iloc[0]["symbol"] == "AAA"
