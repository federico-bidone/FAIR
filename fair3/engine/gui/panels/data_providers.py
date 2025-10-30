"""Panel for manual data-provider ingest operations."""

from __future__ import annotations

from typing import Iterable

from fair3.engine.ingest import available_sources

try:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtCore = QtWidgets = None  # type: ignore[assignment]


class DataProvidersPanel(QtWidgets.QWidget):  # type: ignore[misc]
    """Allow operators to trigger manual ingest tasks."""

    ingestRequested = QtCore.Signal(str, tuple, object)  # type: ignore[call-arg]

    def __init__(self) -> None:
        if QtWidgets is None:  # pragma: no cover
            raise RuntimeError("PySide6 required for DataProvidersPanel")
        super().__init__()
        layout = QtWidgets.QFormLayout(self)

        self._source = QtWidgets.QComboBox()
        self._source.addItems(sorted(available_sources()))
        layout.addRow("Sorgente dati", self._source)

        self._symbols = QtWidgets.QLineEdit()
        self._symbols.setPlaceholderText("Ticker separati da virgola (opzionale)")
        layout.addRow("Simboli", self._symbols)

        self._start = QtWidgets.QDateEdit()
        self._start.setCalendarPopup(True)
        self._start.setDisplayFormat("yyyy-MM-dd")
        self._start.setDate(QtCore.QDate.currentDate().addYears(-1))
        layout.addRow("Data iniziale", self._start)

        self._submit = QtWidgets.QPushButton("Scarica serie storiche")
        self._submit.clicked.connect(self._emit_request)
        layout.addRow(self._submit)

    def _emit_request(self) -> None:
        source = self._source.currentText()
        symbols = tuple(self._parse_symbols(self._symbols.text()))
        start = self._start.date().toPyDate()
        self.ingestRequested.emit(source, symbols, start)

    @staticmethod
    def _parse_symbols(value: str) -> Iterable[str]:
        for chunk in value.split(","):
            cleaned = chunk.strip()
            if cleaned:
                yield cleaned


__all__ = ["DataProvidersPanel"]
