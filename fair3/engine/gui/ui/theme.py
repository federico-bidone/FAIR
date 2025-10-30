"""Simple token-driven stylesheet generator for the FAIR GUI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TOKEN_PATH = Path(__file__).with_name("tokens.json")


def load_tokens(path: Path | str | None = None) -> dict[str, Any]:
    """Load design tokens from disk."""

    location = Path(path) if path is not None else TOKEN_PATH
    with location.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve(token_map: dict[str, Any], key: str, fallback: str) -> str:
    value = token_map.get(key, fallback)
    return str(value)


def build_stylesheet(tokens: dict[str, Any] | None = None) -> str:
    """Return a QSS stylesheet composed from design tokens."""

    tokens = tokens or load_tokens()
    primary = _resolve(tokens, "color.primary", "#0A84FF")
    surface = _resolve(tokens, "color.surface", "rgba(26,32,44,0.85)")
    text = _resolve(tokens, "color.text", "#F2F2F2")
    font_family = _resolve(tokens, "font.family", "Inter")
    radius_small = _resolve(tokens, "radius.small", "6")
    radius_large = _resolve(tokens, "radius.large", "12")

    return f"""
    QWidget {{
        font-family: {font_family};
        color: {text};
        background-color: {surface};
    }}
    QPushButton {{
        background-color: {primary};
        border-radius: {radius_small}px;
        padding: 6px 12px;
    }}
    QPushButton:hover {{
        background-color: lighten({primary}, 10%);
    }}
    QGroupBox {{
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: {radius_large}px;
        margin-top: 12px;
        padding: 12px;
    }}
    QLineEdit, QPlainTextEdit, QTextEdit {{
        background: rgba(0, 0, 0, 0.3);
        border-radius: {radius_small}px;
        padding: 6px;
    }}
    QTabWidget::pane {{
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: {radius_large}px;
    }}
    QStatusBar {{
        background: rgba(0, 0, 0, 0.3);
    }}
    """


def apply_tokens(path: Path | str | None = None) -> str:
    """Load tokens and return a stylesheet ready to be applied."""

    tokens = load_tokens(path)
    return build_stylesheet(tokens)


__all__ = ["apply_tokens", "build_stylesheet", "load_tokens"]
