"""Panel to browse and inspect generated reports."""

from __future__ import annotations

import json
from pathlib import Path

from fair3.engine.infra.paths import DEFAULT_REPORT_ROOT

try:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtCore = QtGui = QtWidgets = None  # type: ignore[assignment]


class ReportsPanel(QtWidgets.QWidget):  # type: ignore[misc]
    """Display report runs, key metrics, and open artefacts."""

    def __init__(self, root: Path | None = None) -> None:
        if QtWidgets is None:  # pragma: no cover
            raise RuntimeError("PySide6 required for ReportsPanel")
        super().__init__()
        self._root = Path(root) if root is not None else DEFAULT_REPORT_ROOT

        layout = QtWidgets.QVBoxLayout(self)

        self._runs = QtWidgets.QListWidget()
        self._runs.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._runs.currentItemChanged.connect(self._display_run)
        layout.addWidget(self._runs)

        splitter = QtWidgets.QSplitter()
        splitter.setOrientation(QtCore.Qt.Horizontal)

        self._files = QtWidgets.QListWidget()
        self._files.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._files.itemDoubleClicked.connect(self._open_file)
        splitter.addWidget(self._files)

        self._details = QtWidgets.QPlainTextEdit()
        self._details.setReadOnly(True)
        self._details.setPlaceholderText("Seleziona un report per vedere i dettagli")
        splitter.addWidget(self._details)

        splitter.setSizes([200, 400])
        layout.addWidget(splitter)

        button_row = QtWidgets.QHBoxLayout()
        self._refresh = QtWidgets.QPushButton("Aggiorna")
        self._refresh.clicked.connect(self.refresh)
        button_row.addWidget(self._refresh)

        self._open = QtWidgets.QPushButton("Apri artefatto")
        self._open.clicked.connect(self._open_selected_file)
        button_row.addWidget(self._open)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        self._runs.clear()
        self._files.clear()
        self._details.clear()
        if not self._root.exists():
            return
        for entry in sorted(self._root.iterdir(), reverse=True):
            if entry.is_dir():
                item = QtWidgets.QListWidgetItem(entry.name)
                item.setData(QtCore.Qt.UserRole, str(entry))
                self._runs.addItem(item)

    def focus_on(self, run: Path) -> None:
        target = run.resolve()
        for index in range(self._runs.count()):
            item = self._runs.item(index)
            stored = item.data(QtCore.Qt.UserRole)
            if stored and Path(stored).resolve() == target:
                self._runs.setCurrentItem(item)
                return

    def _display_run(self, current: QtWidgets.QListWidgetItem | None, _: QtWidgets.QListWidgetItem | None) -> None:
        self._files.clear()
        self._details.clear()
        if current is None:
            return
        path_str = current.data(QtCore.Qt.UserRole)
        if not path_str:
            return
        run_path = Path(path_str)
        if not run_path.exists():
            return

        for artefact in self._collect_files(run_path):
            entry = QtWidgets.QListWidgetItem(artefact.name)
            entry.setData(QtCore.Qt.UserRole, str(artefact))
            self._files.addItem(entry)

        self._details.setPlainText(self._format_details(run_path))

    def _collect_files(self, run_path: Path) -> list[Path]:
        patterns = ("*.pdf", "*.html", "*.csv", "*.json", "*.png")
        results: list[Path] = []
        for pattern in patterns:
            results.extend(sorted(run_path.glob(pattern)))
        return results

    def _format_details(self, run_path: Path) -> str:
        summary_lines = [f"Cartella report: {run_path}"]
        summary_path = run_path / "summary.json"
        if summary_path.exists():
            try:
                with summary_path.open("r", encoding="utf-8") as handle:
                    summary = json.load(handle)
                summary_lines.append("\nMetriche principali:")
                for key, value in summary.items():
                    summary_lines.append(f" - {key}: {value}")
            except (json.JSONDecodeError, OSError):  # pragma: no cover - difesa
                summary_lines.append("Impossibile leggere summary.json")
        else:
            summary_lines.append("Nessun summary.json disponibile")
        pdfs = list(run_path.glob("*.pdf"))
        if pdfs:
            summary_lines.append("\nPDF generati:")
            for pdf in pdfs:
                summary_lines.append(f" - {pdf.name}")
        return "\n".join(summary_lines)

    def _open_selected_file(self) -> None:
        item = self._files.currentItem()
        if item is None:
            return
        self._open_item(item)

    def _open_file(self, item: QtWidgets.QListWidgetItem) -> None:
        self._open_item(item)

    def _open_item(self, item: QtWidgets.QListWidgetItem) -> None:
        path_str = item.data(QtCore.Qt.UserRole)
        if not path_str:
            return
        url = QtCore.QUrl.fromLocalFile(path_str)
        QtGui.QDesktopServices.openUrl(url)


__all__ = ["ReportsPanel"]
