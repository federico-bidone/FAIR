from __future__ import annotations

"""Componenti di quality assurance per il flusso ETL."""

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from fair3.engine.utils.io import ensure_dir

__all__ = ["QARecord", "QAReport", "write_qa_log"]


@dataclass(slots=True)
class QARecord:
    """Snapshot di qualità dati per una coppia simbolo/sorgente.

    Tracciamo periodo coperto, numero di righe utili, valori nulli e outlier
    rimossi così da avere un audit ripetibile dell'intero ETL.  I campi `start`
    ed `end` sono opzionali perché alcune serie potrebbero risultare vuote.
    """

    symbol: str
    source: str
    currency: str
    start: datetime | None
    end: datetime | None
    rows: int
    nulls: int
    outliers: int


@dataclass(slots=True)
class QAReport:
    """Collezione mutabile di record QA con helper per export."""

    records: list[QARecord]

    def to_frame(self) -> pd.DataFrame:
        """Esporta i record QA in `DataFrame` ordinabile."""

        return pd.DataFrame([asdict(record) for record in self.records])

    def append(self, record: QARecord) -> None:
        """Aggiunge un record preservando l'ordine di inserimento."""

        self.records.append(record)


def write_qa_log(report: QAReport, path: Path) -> Path:
    """Scrive il log QA su CSV creando le directory mancanti.

    Se il report è vuoto generiamo comunque l'intestazione per facilitare la
    consultazione manuale e l'import in strumenti BI.  Il file viene ordinato
    per `symbol` e `source` così da avere confronti deterministici nei test.
    """

    ensure_dir(path.parent)
    frame = report.to_frame()
    if frame.empty:
        frame = pd.DataFrame(
            columns=[
                "symbol",
                "source",
                "currency",
                "start",
                "end",
                "rows",
                "nulls",
                "outliers",
            ]
        )
    # Ordiniamo per chiavi leggibili così che i diff del file siano stabili.
    frame = frame.sort_values(["symbol", "source"]).reset_index(drop=True)
    frame.to_csv(path, index=False)
    return path
