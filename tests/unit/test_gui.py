"""Tests for the optional PySide6 GUI integration."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from fair3.engine.gui import launch_gui


class _DummySignal:
    """Minimal signal stub exposing a Qt-compatible connect API."""

    def __init__(self) -> None:
        self._callback: Callable[..., object] | None = None

    def connect(self, callback: Callable[..., object]) -> None:
        """Store the callback without invoking it.

        Args:
            callback: Callable invoked in response to signal emission.

        Returns:
            None.
        """

        self._callback = callback


class _DummyWidget:
    """Base widget that ignores all positional and keyword arguments."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._layout = None

    def setLayout(self, layout: object) -> None:  # noqa: N802
        self._layout = layout

    def addTab(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def addWidget(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def addLayout(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def addRow(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def resize(self, *args: object, **kwargs: object) -> None:
        return None

    def setCentralWidget(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def setWindowTitle(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def show(self) -> None:
        return None


class _DummyPlainTextEdit(_DummyWidget):
    """Plain text edit widget that records appended messages."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.text: list[str] = []

    def setReadOnly(self, *_: object, **__: object) -> None:  # noqa: N802
        return None

    def appendPlainText(self, value: str) -> None:  # noqa: N802
        self.text.append(value)


class _DummyComboBox(_DummyWidget):
    """Combo box storing the provided options for inspection."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._items: list[str] = []
        self._index = 0

    def addItems(self, items: list[str]) -> None:  # noqa: N802
        self._items.extend(items)

    def currentText(self) -> str:  # noqa: N802
        if not self._items:
            return ""
        return self._items[self._index]


class _DummyLineEdit(_DummyWidget):
    """Line edit recording the entered text value."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._text = ""

    def setPlaceholderText(self, *_: object, **__: object) -> None:  # noqa: N802
        return None

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:  # noqa: D401 - short getter description
        """Return the stored string value."""

        return self._text


class _DummyPushButton(_DummyWidget):
    """Push button exposing a dummy clicked signal."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.clicked = _DummySignal()


class _DummyLayout(_DummyWidget):
    """Layout placeholder that ignores all operations."""


class _DummyApplication:
    """Application stub returning immediately on exec()."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        return None

    def exec(self) -> int:
        return 0


class _DummyMainWindow(_DummyWidget):
    """Main window stub inheriting behaviour from the generic widget."""


def _install_qt_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject PySide6.QtWidgets stubs into sys.modules.

    Args:
        monkeypatch: Pytest monkeypatch fixture used to mutate sys.modules.

    Returns:
        None.
    """

    qtwidgets = ModuleType("PySide6.QtWidgets")
    qtwidgets.QApplication = _DummyApplication
    qtwidgets.QMainWindow = _DummyMainWindow
    qtwidgets.QWidget = _DummyWidget
    qtwidgets.QPlainTextEdit = _DummyPlainTextEdit
    qtwidgets.QTabWidget = _DummyWidget
    qtwidgets.QVBoxLayout = _DummyLayout
    qtwidgets.QFormLayout = _DummyLayout
    qtwidgets.QGridLayout = _DummyLayout
    qtwidgets.QComboBox = _DummyComboBox
    qtwidgets.QLineEdit = _DummyLineEdit
    qtwidgets.QPushButton = _DummyPushButton

    root = ModuleType("PySide6")
    root.QtWidgets = qtwidgets
    monkeypatch.dict(sys.modules, {"PySide6": root, "PySide6.QtWidgets": qtwidgets})


def test_launch_gui_missing_dependency(caplog: pytest.LogCaptureFixture) -> None:
    """The GUI returns immediately when PySide6 is not installed."""

    sys.modules.pop("PySide6", None)
    caplog.set_level("INFO")
    launch_gui({})
    assert any("PySide6 not installed" in record.message for record in caplog.records)


def test_launch_gui_smoke_with_stubs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A stubbed PySide6 environment allows the GUI to initialise."""

    _install_qt_stubs(monkeypatch)
    launch_gui({"report_path": tmp_path / "report.pdf"})
