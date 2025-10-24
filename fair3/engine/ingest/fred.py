from __future__ import annotations

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["FREDFetcher"]


class FREDFetcher(BaseCSVFetcher):
    """Download FRED series using the public CSV endpoint."""

    SOURCE = "fred"
    LICENSE = "Federal Reserve Economic Data (FRED) Terms of Use"
    BASE_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    HEADERS = {
        "Accept": "text/csv, */*;q=0.1",
        "User-Agent": "fair3/0.1 (+https://github.com/federico-bidone/FAIR)",
    }
    DEFAULT_SYMBOLS = ("DGS10", "DCOILWTICO")

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        params: list[str] = [f"id={symbol}"]
        if start is not None:
            params.append(f"observation_start={start.date():%Y-%m-%d}")
        return f"{self.BASE_URL}?{'&'.join(params)}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        if payload.lstrip().startswith("<"):
            msg = "FRED: non-CSV payload (HTML) ricevuto; probabile rate-limit o errore endpoint"
            raise ValueError(msg)
        payload = payload.lstrip("\ufeff")
        first = payload.split("\n", 1)[0]
        cols = [c.strip() for c in first.split(",")]
        header_upper = [c.upper() for c in cols]
        if symbol.upper() in header_upper:
            value_column = symbol
        elif "VALUE" in header_upper:
            value_column = "VALUE"
        else:
            msg = f"FRED: header inatteso {cols[:2]}...; atteso DATE+{symbol} o DATE+VALUE"
            raise ValueError(msg)
        frame = self._simple_frame(
            payload,
            symbol,
            date_column="DATE",
            value_column=value_column,
        )
        # FRED encodes missing data as "."; ``pd.to_numeric`` already coerces them to NaN.
        frame["value"] = frame["value"].astype(float)
        return frame
