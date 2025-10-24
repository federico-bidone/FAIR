from __future__ import annotations

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["StooqFetcher"]


class StooqFetcher(BaseCSVFetcher):
    """Download end-of-day prices from Stooq."""

    SOURCE = "stooq"
    LICENSE = "Stooq.com data usage policy"
    BASE_URL = "https://stooq.com/q/d/l/"
    DEFAULT_SYMBOLS = ("spx",)

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        ticker = symbol.upper()
        params: list[str] = [f"s={ticker}", "i=d"]
        return f"{self.BASE_URL}?{'&'.join(params)}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        if payload.lstrip().startswith("<"):
            msg = "Stooq: payload HTML (ticker inesistente o endpoint non CSV)"
            raise ValueError(msg)
        lines = payload.splitlines()
        if lines:
            header_parts = [part.strip() for part in lines[0].split(",")]
            lines[0] = ",".join(header_parts)
            payload = "\n".join(lines)
        frame = self._simple_frame(
            payload,
            symbol,
            date_column="Date",
            value_column="Close",
        )
        frame["value"] = frame["value"].astype(float)
        return frame
