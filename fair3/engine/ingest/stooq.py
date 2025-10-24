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
        params: list[str] = [f"s={symbol.lower()}", "i=d"]
        return f"{self.BASE_URL}?{'&'.join(params)}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        frame = self._simple_frame(
            payload,
            symbol,
            date_column="Date",
            value_column="Close",
        )
        frame["value"] = frame["value"].astype(float)
        return frame
