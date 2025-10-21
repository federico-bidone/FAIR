from __future__ import annotations

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["BOEFetcher"]


class BOEFetcher(BaseCSVFetcher):
    """Download Bank of England datasets via the CSV download interface."""

    SOURCE = "boe"
    LICENSE = "Bank of England Data Services Terms and Conditions"
    BASE_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-getTDDownloadCSV"
    DEFAULT_SYMBOLS = ("IUMGBP",)

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        params: list[str] = [f"SeriesCodes={symbol}", "CSVF=TN", "Using=Y", "VPD=Y"]
        if start is not None:
            params.append(f"From={start.date():%Y-%m-%d}")
        return f"{self.BASE_URL}?{'&'.join(params)}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        frame = self._simple_frame(
            payload,
            symbol,
            date_column="DATE",
            value_column="VALUE",
        )
        frame["value"] = frame["value"].astype(float)
        return frame
