"""Panel to browse and open generated reports."""

from __future__ import annotations

from pathlib import Path

from fair3.engine.infra.paths import DEFAULT_REPORT_ROOT

try:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtCore = QtGui = QtWidgets = None  # type: ignore[assignment]


class ReportsPanel(QtWidgets.QWidget):  # type: ignore[misc]
    """Display a list of generated report folders."""

    def __init__(self, root: Path | None = None) -> None:
        if QtWidgets is None:  # pragma: no cover
            raise RuntimeError("PySide6 required for ReportsPanel")
        super().__init__()
        self._root = Path(root) if root is not None else DEFAULT_REPORT_ROOT

        layout = QtWidgets.QVBoxLayout(self)
        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(self._list)

        button_row = QtWidgets.QHBoxLayout()
        self._refresh = QtWidgets.QPushButton("Aggiorna")
        self._refresh.clicked.connect(self.refresh)
        button_row.addWidget(self._refresh)

        self._open = QtWidgets.QPushButton("Apri cartella")
        self._open.clicked.connect(self._open_selected)
        button_row.addWidget(self._open)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        self._list.clear()
        if not self._root.exists():
            return
        for entry in sorted(self._root.iterdir(), reverse=True):
            if entry.is_dir():
                item = QtWidgets.QListWidgetItem(entry.name)
                item.setData(QtCore.Qt.UserRole, str(entry))
                self._list.addItem(item)

    def _open_selected(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        path_str = item.data(QtCore.Qt.UserRole)
        if not path_str:
            return
        url = QtCore.QUrl.fromLocalFile(path_str)
        QtGui.QDesktopServices.openUrl(url)


__all__ = ["ReportsPanel"]
