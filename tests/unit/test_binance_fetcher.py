"""Test di unità per il fetcher Binance Data Portal."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pytest
import requests

from fair3.engine.ingest.binance import BinanceFetcher

MonkeyPatch = pytest.MonkeyPatch


def _kline_row(
    day: str,
    *,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: float,
    quote_volume: float,
    trades: int,
    taker_buy_base: float,
    taker_buy_quote: float,
) -> list[str]:
    """Costruisce la riga CSV di un kline giornaliero."""

    open_time = pd.Timestamp(day, tz=UTC)
    close_time = open_time + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
    return [
        str(int(open_time.value // 10**6)),
        f"{open_price}",
        f"{high_price}",
        f"{low_price}",
        f"{close_price}",
        f"{volume}",
        str(int(close_time.value // 10**6)),
        f"{quote_volume}",
        str(trades),
        f"{taker_buy_base}",
        f"{taker_buy_quote}",
        "0",
    ]


def _zip_payload(filename: str, rows: list[list[str]]) -> bytes:
    """Serializza le righe in un archivio ZIP compatibile con Binance."""

    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        csv_buffer = io.StringIO()
        for row in rows:
            csv_buffer.write(",".join(row) + "\n")
        archive.writestr(filename, csv_buffer.getvalue())
    return buffer.getvalue()


def test_binance_fetcher_parses_zip_and_filters_dates(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """Il fetcher concatena più giorni e genera metadati coerenti."""

    fetcher = BinanceFetcher(raw_root=tmp_path)
    dates = ["2024-01-01", "2024-01-02"]
    payloads: dict[str, bytes] = {}
    for day in dates:
        url = fetcher._compose_daily_url("BTCUSDT", day)
        payloads[url] = _zip_payload(
            f"BTCUSDT-1d-{day}.csv",
            [
                _kline_row(
                    day,
                    open_price=10.0,
                    high_price=12.0,
                    low_price=9.5,
                    close_price=11.0,
                    volume=100.0,
                    quote_volume=1100.0,
                    trades=42,
                    taker_buy_base=60.0,
                    taker_buy_quote=660.0,
                )
            ],
        )

    monkeypatch.setattr(fetcher, "_download", lambda url, session=None: payloads[url])

    artifact = fetcher.fetch(
        symbols=["BTCUSDT"],
        start=datetime(2024, 1, 1),
        as_of=datetime(2024, 1, 2, tzinfo=UTC),
    )

    assert artifact.data.shape[0] == 2
    assert artifact.data["symbol"].unique().tolist() == ["BTCUSDT"]
    assert artifact.data["value"].tolist() == [11.0, 11.0]
    assert artifact.data["currency"].unique().tolist() == ["USDT"]
    assert artifact.data["interval"].unique().tolist() == ["1d"]
    assert all(flag == 1 for flag in artifact.data["pit_flag"].tolist())
    assert artifact.metadata["license"] == BinanceFetcher.LICENSE
    assert len(artifact.metadata["requests"]) == 2
    statuses = {entry["status"] for entry in artifact.metadata["requests"]}
    assert statuses == {"ok"}


def test_binance_fetcher_skips_missing_days(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    """I 404 giornalieri vengono ignorati lasciando traccia nei metadati."""

    fetcher = BinanceFetcher(raw_root=tmp_path)
    day_ok = "2024-01-01"
    payload_ok = _zip_payload(
        f"BTCUSDT-1d-{day_ok}.csv",
        [
            _kline_row(
                day_ok,
                open_price=10.0,
                high_price=12.0,
                low_price=9.5,
                close_price=11.0,
                volume=100.0,
                quote_volume=1100.0,
                trades=42,
                taker_buy_base=60.0,
                taker_buy_quote=660.0,
            )
        ],
    )

    response = requests.Response()
    response.status_code = 404
    http_error = requests.HTTPError("Not Found")
    http_error.response = response

    def fake_download(url: str, session: object | None = None) -> bytes:
        if "2024-01-02" in url:
            raise http_error
        return payload_ok

    monkeypatch.setattr(fetcher, "_download", fake_download)

    artifact = fetcher.fetch(
        symbols=["BTCUSDT"],
        start=datetime(2024, 1, 1),
        as_of=datetime(2024, 1, 2, tzinfo=UTC),
    )

    assert artifact.data.shape[0] == 1
    assert artifact.data.loc[0, "date"].date().isoformat() == day_ok
    statuses = {entry["status"] for entry in artifact.metadata["requests"]}
    assert statuses == {"ok", "missing"}


def test_binance_parse_rejects_html_payload(tmp_path: Path) -> None:
    """Il parser deve respingere payload HTML tipici di pagine di errore."""

    fetcher = BinanceFetcher(raw_root=tmp_path)
    with pytest.raises(ValueError, match="HTML payload detected"):
        fetcher.parse(b"<html>errore</html>", "BTCUSDT")
