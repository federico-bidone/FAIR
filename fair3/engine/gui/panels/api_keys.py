"""Panel handling API key persistence through the system keyring."""

from __future__ import annotations

from functools import partial
from typing import Mapping

from fair3.engine.infra.secrets import (
    apply_api_keys,
    is_backend_available,
    load_api_keys,
    save_api_keys,
)
from fair3.engine.ingest.registry import CredentialField, credential_fields

try:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtCore = QtWidgets = None  # type: ignore[assignment]

_OPENFIGI_FIELD = CredentialField(
    source="openfigi",
    env="OPENFIGI_API_KEY",
    label="OpenFIGI",
    description="Ticker ↔ ISIN mapping service",
    url="https://www.openfigi.com/api",
)


class APIKeysPanel(QtWidgets.QWidget):  # type: ignore[misc]
    """Provide a secure interface for managing provider API keys."""

    testRequested = QtCore.Signal(str)  # type: ignore[call-arg]

    def __init__(self) -> None:
        if QtWidgets is None:  # pragma: no cover
            raise RuntimeError("PySide6 required for APIKeysPanel")
        super().__init__()
        self._fields: dict[str, QtWidgets.QLineEdit] = {}
        self._mask_labels: dict[str, QtWidgets.QLabel] = {}
        self._source_env: dict[str, str] = {}
        self._descriptions: dict[str, str] = {}
        self._existing: dict[str, str] = {}
        self._modified: set[str] = set()

        layout = QtWidgets.QVBoxLayout(self)
        intro = QtWidgets.QLabel(
            "Le credenziali vengono salvate tramite il keyring del sistema operativo."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if not is_backend_available():
            warning = QtWidgets.QLabel(
                "Keyring non disponibile. Installa le dipendenze GUI per abilitare il salvataggio."
            )
            warning.setWordWrap(True)
            layout.addWidget(warning)

        form = QtWidgets.QFormLayout()
        layout.addLayout(form)

        for field in list(credential_fields()) + [_OPENFIGI_FIELD]:
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            line = QtWidgets.QLineEdit()
            line.setEchoMode(QtWidgets.QLineEdit.Password)
            line.setClearButtonEnabled(True)
            line.setPlaceholderText(field.description)
            line.setToolTip(field.description)
            row_layout.addWidget(line)
            clear_btn = QtWidgets.QPushButton("Cancella")
            clear_btn.clicked.connect(partial(self._clear_value, field.env))
            row_layout.addWidget(clear_btn)
            test_btn = QtWidgets.QPushButton("Test")
            test_btn.clicked.connect(lambda _=False, src=field.source: self.testRequested.emit(src))
            row_layout.addWidget(test_btn)
            mask_label = QtWidgets.QLabel("—")
            mask_label.setObjectName(f"mask_{field.env.lower()}")
            mask_label.setMinimumWidth(80)
            mask_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            row_layout.addWidget(mask_label)
            form.addRow(field.label, row_widget)
            self._fields[field.env] = line
            self._mask_labels[field.env] = mask_label
            self._source_env[field.source] = field.env
            self._descriptions[field.env] = field.description
            line.textEdited.connect(partial(self._mark_modified, field.env))

        self._save_button = QtWidgets.QPushButton("Salva in keyring")
        self._save_button.clicked.connect(self._persist)
        layout.addWidget(self._save_button)

        layout.addStretch(1)
        self.load_existing()

    def load_existing(self) -> None:
        """Populate the fields from the keyring where available."""

        self._existing = load_api_keys()
        apply_api_keys(self._existing)
        self._modified.clear()
        for env, widget in self._fields.items():
            widget.setText("")
            widget.setPlaceholderText(self._descriptions.get(env, ""))
            mask_label = self._mask_labels.get(env)
            if mask_label is not None:
                mask_label.setText(self._mask(self._existing.get(env)))

    def apply_values(self, values: Mapping[str, str]) -> None:
        for env, value in values.items():
            widget = self._fields.get(env)
            if widget is not None:
                widget.setText(value)
                label = self._mask_labels.get(env)
                if label is not None:
                    label.setText("—")
                self._modified.add(env)

    def env_for_source(self, source: str) -> str | None:
        return self._source_env.get(source)

    def _persist(self) -> None:
        updates: dict[str, str | None] = {}
        for env in self._modified:
            widget = self._fields.get(env)
            if widget is None:
                continue
            text = widget.text().strip()
            updates[env] = text if text else None
        if not updates:
            return
        stored = save_api_keys(updates)
        apply_api_keys(stored)
        self._existing = stored
        self._modified.clear()
        for env, widget in self._fields.items():
            widget.clear()
            widget.setPlaceholderText(self._descriptions.get(env, ""))
            mask = self._mask(self._existing.get(env))
            label = self._mask_labels.get(env)
            if label is not None:
                label.setText(mask)

    def _mark_modified(self, env: str, _: str) -> None:
        self._modified.add(env)

    def _clear_value(self, env: str) -> None:
        widget = self._fields.get(env)
        if widget is None:
            return
        widget.clear()
        self._modified.add(env)
        label = self._mask_labels.get(env)
        if label is not None:
            label.setText("—")

    @staticmethod
    def _mask(value: str | None) -> str:
        if not value:
            return "—"
        tail = value[-4:]
        return f"***{tail}"


__all__ = ["APIKeysPanel"]
