from types import SimpleNamespace
import sys
from types import SimpleNamespace

import importlib

import pytest

gui_main_module = importlib.import_module("fair3.engine.gui.main")


def test_launch_gui_skips_without_qt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gui_main_module, "_ensure_qt", lambda: None)
    assert gui_main_module.launch_gui(auto_exec=False) is False


def test_launch_gui_initialises_window(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyApp:
        _instance: "DummyApp | None" = None

        def __init__(self, argv: list[str] | None = None) -> None:
            type(self)._instance = self
            self.argv = argv
            self.stylesheet: str | None = None
            self.exec_called = False

        @classmethod
        def instance(cls) -> "DummyApp | None":
            return cls._instance

        def setStyleSheet(self, value: str) -> None:
            self.stylesheet = value

        def exec(self) -> None:
            self.exec_called = True

    qt_widgets = SimpleNamespace(QApplication=DummyApp)

    class DummyWindow:
        created = 0

        def __init__(self, *, configuration: dict, qt_core: object, qt_gui: object) -> None:
            type(self).created += 1
            self.configuration = configuration
            self.qt_core = qt_core
            self.qt_gui = qt_gui
            self.shown = False

        def show(self) -> None:
            self.shown = True

    dummy_module = SimpleNamespace(FairMainWindow=DummyWindow)
    monkeypatch.setitem(sys.modules, "fair3.engine.gui.mainwindow", dummy_module)
    monkeypatch.setattr(gui_main_module, "_ensure_qt", lambda: (object(), object(), qt_widgets))

    launched = gui_main_module.launch_gui(auto_exec=False)
    assert launched is True
    assert DummyWindow.created == 1
    app = DummyApp.instance()
    assert app is not None and app.stylesheet is not None
