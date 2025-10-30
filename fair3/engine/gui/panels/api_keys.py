"""Panel handling API key persistence through the system keyring."""

from __future__ import annotations

from typing import Mapping

from fair3.engine.infra.secrets import get_secret, is_backend_available, set_secret
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
        self._source_env: dict[str, str] = {}

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
            line.setPlaceholderText(field.description)
            row_layout.addWidget(line)
            test_btn = QtWidgets.QPushButton("Test")
            test_btn.clicked.connect(lambda _=False, src=field.source: self.testRequested.emit(src))
            row_layout.addWidget(test_btn)
            form.addRow(field.label, row_widget)
            self._fields[field.env] = line
            self._source_env[field.source] = field.env

        self._save_button = QtWidgets.QPushButton("Salva in keyring")
        self._save_button.clicked.connect(self._persist)
        layout.addWidget(self._save_button)

        layout.addStretch(1)
        self.load_existing()

    def load_existing(self) -> None:
        """Populate the fields from the keyring where available."""

        for env, widget in self._fields.items():
            value = get_secret(service=env.lower(), username="default")
            if value:
                widget.setText(value)

    def apply_values(self, values: Mapping[str, str]) -> None:
        for env, value in values.items():
            widget = self._fields.get(env)
            if widget is not None:
                widget.setText(value)

    def env_for_source(self, source: str) -> str | None:
        return self._source_env.get(source)

    def _persist(self) -> None:
        for env, widget in self._fields.items():
            value = widget.text().strip()
            if value:
                set_secret(service=env.lower(), username="default", value=value)
            else:
                set_secret(service=env.lower(), username="default", value=None)


__all__ = ["APIKeysPanel"]
