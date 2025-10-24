from __future__ import annotations

from datetime import datetime
from io import StringIO
from urllib.parse import urlencode

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["BOEFetcher"]


class BOEFetcher(BaseCSVFetcher):
    """Download Bank of England datasets via the CSV download interface."""

    SOURCE = "boe"
    LICENSE = "Bank of England Data Services Terms and Conditions"
    BASE_URL = "https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp"
    DEFAULT_SYMBOLS = ("IUMGBP",)

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        if start is None:
            start_string = "01/Jan/1900"
        else:
            if hasattr(start, "to_pydatetime"):
                start_dt = start.to_pydatetime()
            else:
                start_dt = datetime.combine(start, datetime.min.time())
            start_string = start_dt.strftime("%d/%b/%Y")
        params = {
            "csv.x": "yes",
            "Datefrom": start_string,
            "Dateto": "now",
            "SeriesCodes": symbol,
            "UsingCodes": "Y",
            "CSVF": "TN",
        }
        return f"{self.BASE_URL}?{urlencode(params)}"

    def _validate_payload(self, payload: str) -> None:
        stripped = payload.lstrip("\ufeff\n\r ")
        if stripped.startswith("<") or "," not in payload:
            msg = "BoE: payload HTML o non-CSV (serie errata/endpoint cambiato)"
            raise ValueError(msg)

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        self._validate_payload(payload)
        csv = pd.read_csv(StringIO(payload), header=None, names=["date", "value"], usecols=[0, 1])
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(csv["date"], dayfirst=True, errors="coerce"),
                "value": pd.to_numeric(csv["value"], errors="coerce"),
                "symbol": symbol,
            }
        )
        frame = frame.dropna(subset=["date"]).reset_index(drop=True)
        frame["value"] = frame["value"].astype(float)
        return frame
