from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from fair3.engine.utils.io import ensure_dir

__all__ = ["QARecord", "QAReport", "write_qa_log"]


@dataclass(slots=True)
class QARecord:
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
    records: list[QARecord]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame([asdict(record) for record in self.records])

    def append(self, record: QARecord) -> None:
        self.records.append(record)


def write_qa_log(report: QAReport, path: Path) -> Path:
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
    frame = frame.sort_values(["symbol", "source"]).reset_index(drop=True)
    frame.to_csv(path, index=False)
    return path
