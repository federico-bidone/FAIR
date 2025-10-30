"""Pipeline orchestration panel."""

from __future__ import annotations

from typing import Iterable

from fair3.engine.ingest import available_sources

try:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtCore = QtWidgets = None  # type: ignore[assignment]


class PipelinePanel(QtWidgets.QWidget):  # type: ignore[misc]
    """Expose manual and automatic orchestration controls."""

    manualRequested = QtCore.Signal(dict)  # type: ignore[call-arg]
    automaticRequested = QtCore.Signal(dict)  # type: ignore[call-arg]

    def __init__(self) -> None:
        if QtWidgets is None:  # pragma: no cover
            raise RuntimeError("PySide6 required for PipelinePanel")
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)

        manual_group = QtWidgets.QGroupBox("Modalità manuale")
        manual_layout = QtWidgets.QFormLayout(manual_group)
        self._manual_provider = QtWidgets.QComboBox()
        self._manual_provider.addItems(sorted(available_sources()))
        manual_layout.addRow("Provider", self._manual_provider)
        self._manual_symbols = QtWidgets.QLineEdit()
        self._manual_symbols.setPlaceholderText("Ticker separati da virgola")
        manual_layout.addRow("Simboli", self._manual_symbols)
        self._manual_start = QtWidgets.QDateEdit()
        self._manual_start.setCalendarPopup(True)
        self._manual_start.setDisplayFormat("yyyy-MM-dd")
        self._manual_start.setDate(QtCore.QDate.currentDate().addYears(-3))
        manual_layout.addRow("Data inizio", self._manual_start)
        self._manual_run = QtWidgets.QPushButton("Esegui ingest manuale")
        self._manual_run.clicked.connect(self._emit_manual)
        manual_layout.addRow(self._manual_run)
        layout.addWidget(manual_group)

        auto_group = QtWidgets.QGroupBox("Modalità automatica")
        auto_layout = QtWidgets.QFormLayout(auto_group)
        self._auto_start = QtWidgets.QDateEdit()
        self._auto_start.setCalendarPopup(True)
        self._auto_start.setDisplayFormat("yyyy-MM-dd")
        self._auto_start.setDate(QtCore.QDate.currentDate().addYears(-5))
        auto_layout.addRow("Storico minimo", self._auto_start)
        self._auto_generate_reports = QtWidgets.QCheckBox(
            "Genera report mensili al termine"
        )
        self._auto_generate_reports.setChecked(True)
        auto_layout.addRow(self._auto_generate_reports)
        self._auto_run = QtWidgets.QPushButton("Avvia orchestrazione completa")
        self._auto_run.clicked.connect(self._emit_auto)
        auto_layout.addRow(self._auto_run)
        layout.addWidget(auto_group)

        layout.addStretch(1)

    def _emit_manual(self) -> None:
        provider = self._manual_provider.currentText()
        symbols = tuple(self._parse_symbols(self._manual_symbols.text()))
        start = self._manual_start.date().toPyDate()
        payload = {"mode": "manual", "provider": provider, "symbols": symbols, "start": start}
        self.manualRequested.emit(payload)

    def _emit_auto(self) -> None:
        start = self._auto_start.date().toPyDate()
        payload = {
            "mode": "automatic",
            "start": start,
            "generate_reports": self._auto_generate_reports.isChecked(),
        }
        self.automaticRequested.emit(payload)

    @staticmethod
    def _parse_symbols(value: str) -> Iterable[str]:
        for token in value.split(","):
            cleaned = token.strip()
            if cleaned:
                yield cleaned


__all__ = ["PipelinePanel"]
