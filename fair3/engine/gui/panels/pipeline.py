"""Pipeline orchestration panel."""

from __future__ import annotations

from datetime import date as _date
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
        steps_widget = QtWidgets.QWidget()
        steps_layout = QtWidgets.QVBoxLayout(steps_widget)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        self._step_universe = QtWidgets.QCheckBox("Scopri universo (broker selezionati)")
        self._step_universe.setChecked(True)
        steps_layout.addWidget(self._step_universe)
        self._step_ingest = QtWidgets.QCheckBox("Scarica dati (seleziona provider)")
        self._step_ingest.setChecked(True)
        steps_layout.addWidget(self._step_ingest)
        self._step_etl = QtWidgets.QCheckBox("Costruisci pannello ETL")
        self._step_etl.setChecked(True)
        steps_layout.addWidget(self._step_etl)
        self._step_factors = QtWidgets.QCheckBox("Calcola fattori")
        self._step_factors.setChecked(True)
        steps_layout.addWidget(self._step_factors)
        self._step_estimates = QtWidgets.QCheckBox("Stima rendimenti e covarianza")
        self._step_estimates.setChecked(True)
        steps_layout.addWidget(self._step_estimates)
        self._step_report = QtWidgets.QCheckBox("Genera report mensile")
        self._step_report.setChecked(True)
        steps_layout.addWidget(self._step_report)
        manual_layout.addRow("Fasi", steps_widget)

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
        self._manual_brokers = QtWidgets.QLineEdit()
        self._manual_brokers.setPlaceholderText("Broker separati da virgola (opzionale)")
        manual_layout.addRow("Broker", self._manual_brokers)
        self._manual_reports = QtWidgets.QCheckBox("Genera report (se selezionato)")
        self._manual_reports.setChecked(True)
        manual_layout.addRow("Report", self._manual_reports)
        self._manual_run = QtWidgets.QPushButton("Esegui pipeline personalizzata")
        self._manual_run.clicked.connect(self._emit_manual)
        manual_layout.addRow(self._manual_run)
        self._step_ingest.toggled.connect(self._toggle_ingest_controls)
        self._step_report.toggled.connect(self._manual_reports.setEnabled)
        self._step_report.toggled.connect(self._sync_report_checkbox)
        self._toggle_ingest_controls(self._step_ingest.isChecked())
        self._manual_reports.setEnabled(self._step_report.isChecked())
        self._sync_report_checkbox(self._step_report.isChecked())
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
        manual_qdate = self._manual_start.date()
        # PySide6: QDate.toPython() compat; fallback manuale per versioni senza toPython.
        start = (
            manual_qdate.toPython()
            if hasattr(manual_qdate, "toPython")
            else _date(manual_qdate.year(), manual_qdate.month(), manual_qdate.day())
        )
        steps = self._selected_steps()
        brokers = tuple(self._parse_symbols(self._manual_brokers.text()))
        payload = {
            "mode": "manual",
            "provider": provider if "ingest" in steps else None,
            "symbols": symbols if "ingest" in steps else (),
            "start": start,
            "steps": steps,
            "brokers": brokers,
            "generate_reports": self._manual_reports.isChecked(),
        }
        self.manualRequested.emit(payload)

    def _emit_auto(self) -> None:
        auto_qdate = self._auto_start.date()
        # PySide6: QDate.toPython() compat; fallback manuale per versioni senza toPython.
        start = (
            auto_qdate.toPython()
            if hasattr(auto_qdate, "toPython")
            else _date(auto_qdate.year(), auto_qdate.month(), auto_qdate.day())
        )
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

    def _selected_steps(self) -> tuple[str, ...]:
        mapping = {
            "universe": self._step_universe,
            "ingest": self._step_ingest,
            "etl": self._step_etl,
            "factors": self._step_factors,
            "estimates": self._step_estimates,
            "report": self._step_report,
        }
        return tuple(name for name, checkbox in mapping.items() if checkbox.isChecked())

    def _toggle_ingest_controls(self, checked: bool) -> None:
        self._manual_provider.setEnabled(checked)
        self._manual_symbols.setEnabled(checked)
        self._manual_start.setEnabled(checked)

    def _sync_report_checkbox(self, checked: bool) -> None:
        if not checked:
            self._manual_reports.setChecked(False)
        else:
            if not self._manual_reports.isChecked():
                self._manual_reports.setChecked(True)


__all__ = ["PipelinePanel"]
