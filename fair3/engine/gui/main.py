"""Entry point for the optional FAIR-III Qt GUI."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

LOG = logging.getLogger(__name__)

_INSTALL_HINT = "pip install .[gui]"


def _ensure_qt() -> tuple[object, object, object] | None:
    """Attempt to import the Qt bindings used by the GUI."""

    try:  # pragma: no cover - optional dependency resolution
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError as exc:  # pragma: no cover - optional dependency resolution
        LOG.error(
            "PySide6 is not installed. Install the GUI extras via `%s`. (%s)",
            _INSTALL_HINT,
            exc,
        )
        return None
    return QtCore, QtGui, QtWidgets


def _maybe_apply_theme(app: "QtWidgets.QApplication") -> None:
    """Load the design tokens and apply the stylesheet."""

    from .ui.theme import apply_tokens

    try:
        stylesheet = apply_tokens()
    except Exception as exc:  # pragma: no cover - defensive guard
        LOG.warning("Unable to apply GUI theme: %s", exc)
        return
    app.setStyleSheet(stylesheet)



def launch_gui(
    cfg: dict[str, Any] | None = None,
    *,
    auto_exec: bool = True,
) -> bool:
    """Launch the FAIR GUI if the Qt bindings are available."""

    qt_modules = _ensure_qt()
    if qt_modules is None:
        return False
    QtCore, QtGui, QtWidgets = qt_modules
    from .mainwindow import FairMainWindow

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv or ["fair3-gui"])
    _maybe_apply_theme(app)

    window = FairMainWindow(configuration=cfg or {}, qt_core=QtCore, qt_gui=QtGui)
    window.show()
    if auto_exec:
        app.exec()
    return True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FAIR-III GUI launcher")
    parser.add_argument(
        "--no-exec",
        action="store_true",
        help="Initialise the GUI without starting the Qt event loop (testing)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Console script entry point used by `fair3-gui`."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    launched = launch_gui(auto_exec=not args.no_exec)
    return 0 if launched else 1


__all__ = ["launch_gui", "main"]
