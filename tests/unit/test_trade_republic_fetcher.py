"""Tests for the Trade Republic broker universe fetcher."""

from __future__ import annotations

import io

import pytest
from pytest import MonkeyPatch
from reportlab.pdfgen import canvas

from fair3.engine.brokers import TradeRepublicFetcher

pytest.importorskip("pdfplumber")


def _make_pdf(lines: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    text = pdf.beginText(40, 800)
    for line in lines:
        text.textLine(line)
    pdf.drawText(text)
    pdf.save()
    return buffer.getvalue()


def test_trade_republic_fetcher_parses_pdf(monkeypatch: MonkeyPatch) -> None:
    lines = [
        "TRADING UNIVERSE 2024",
        "Stocks",
        "ISIN Name",
        "DE0001234560 ACME AG",
        "ETF",
        "IE00B0M62Q58 Vanguard FTSE All-World UCITS ETF",
    ]
    payload = _make_pdf(lines)
    fetcher = TradeRepublicFetcher()
    monkeypatch.setattr(fetcher, "_download_pdf", lambda url: payload)
    artifact = fetcher.fetch_universe()
    assert artifact.broker == fetcher.BROKER
    assert {"isin", "name", "section", "asset_class"}.issubset(artifact.frame.columns)
    assert set(artifact.frame["isin"]) == {"DE0001234560", "IE00B0M62Q58"}
    assert (
        artifact.frame.loc[artifact.frame["isin"] == "DE0001234560", "asset_class"].iloc[0]
        == "Equity"
    )


def test_trade_republic_fetcher_respects_allowed_sections(monkeypatch: MonkeyPatch) -> None:
    lines = [
        "Stocks",
        "ISIN Name",
        "DE0001234560 ACME AG",
        "ETF",
        "IE00B0M62Q58 Vanguard FTSE All-World UCITS ETF",
    ]
    payload = _make_pdf(lines)
    fetcher = TradeRepublicFetcher(allowed_sections=("ETF",))
    monkeypatch.setattr(fetcher, "_download_pdf", lambda url: payload)
    artifact = fetcher.fetch_universe()
    assert artifact.frame["isin"].tolist() == ["IE00B0M62Q58"]
