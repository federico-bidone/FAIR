"""Broker discovery panel."""

from __future__ import annotations

from typing import Sequence

from fair3.engine.brokers import available_brokers

try:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtCore = QtWidgets = None  # type: ignore[assignment]


class BrokersPanel(QtWidgets.QWidget):  # type: ignore[misc]
    """Expose broker discovery and universe aggregation controls."""

    discoverRequested = QtCore.Signal(tuple)  # type: ignore[call-arg]

    def __init__(self) -> None:
        if QtWidgets is None:  # pragma: no cover - sanity guard
            raise RuntimeError("PySide6 is required to instantiate BrokersPanel")
        super().__init__()
        self.setObjectName("brokersPanel")
        layout = QtWidgets.QVBoxLayout(self)

        description = QtWidgets.QLabel(
            "Seleziona i broker da cui estrarre l'universo investibile."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self._list = QtWidgets.QListWidget()
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        layout.addWidget(self._list)

        selection_row = QtWidgets.QHBoxLayout()
        select_all = QtWidgets.QPushButton("Seleziona tutti")
        select_all.clicked.connect(lambda: self._set_all(True))
        selection_row.addWidget(select_all)
        select_none = QtWidgets.QPushButton("Deseleziona tutti")
        select_none.clicked.connect(lambda: self._set_all(False))
        selection_row.addWidget(select_none)
        selection_row.addStretch(1)
        layout.addLayout(selection_row)

        button_row = QtWidgets.QHBoxLayout()
        self._refresh = QtWidgets.QPushButton("Aggiorna elenco broker")
        self._refresh.clicked.connect(self.refresh)
        button_row.addWidget(self._refresh)

        self._discover = QtWidgets.QPushButton("Costruisci universo")
        self._discover.clicked.connect(self._emit_selection)
        button_row.addWidget(self._discover)

        button_row.addStretch(1)
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self) -> None:
        """Populate the list widget with the current broker registry."""

        self._list.clear()
        for broker in sorted(available_brokers()):
            item = QtWidgets.QListWidgetItem(broker)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            self._list.addItem(item)

    def selected_brokers(self) -> tuple[str, ...]:
        """Return the brokers currently ticked in the UI."""

        selected: list[str] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.checkState() == QtCore.Qt.Checked:
                selected.append(item.text())
        return tuple(selected)

    def set_selected(self, brokers: Sequence[str]) -> None:
        target = set(brokers)
        for index in range(self._list.count()):
            item = self._list.item(index)
            item.setCheckState(
                QtCore.Qt.Checked if item.text() in target else QtCore.Qt.Unchecked
            )

    def _emit_selection(self) -> None:
        brokers = self.selected_brokers()
        self.discoverRequested.emit(brokers)

    def _set_all(self, checked: bool) -> None:
        state = QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked
        for index in range(self._list.count()):
            item = self._list.item(index)
            item.setCheckState(state)


__all__ = ["BrokersPanel"]
