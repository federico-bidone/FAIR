from __future__ import annotations

import io
import json
import logging
import os
from urllib.parse import urlencode
from zipfile import BadZipFile, ZipFile

import pandas as pd
import requests

from .registry import BaseCSVFetcher

__all__ = ["FREDFetcher"]


class FREDFetcher(BaseCSVFetcher):
    """Download FRED series using the official observations API."""

    SOURCE = "fred"
    LICENSE = "Federal Reserve Economic Data (FRED) Terms of Use"
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    HEADERS = {
        "Accept": "application/json, application/zip;q=0.9, text/csv;q=0.8, */*;q=0.1",
        "User-Agent": "fair3/0.1 (+https://github.com/federico-bidone/FAIR)",
    }
    DEFAULT_SYMBOLS = ("DGS10", "DCOILWTICO")

    def __init__(
        self,
        *,
        file_type: str = "json",
        raw_root: str | os.PathLike[str] | None = None,
        logger: logging.Logger | None = None,
        session: requests.Session | None = None,
    ) -> None:
        api_key = os.environ.get("FRED_API_KEY")
        if not api_key:
            raise RuntimeError("FRED_API_KEY environment variable is required")
        if len(api_key) != 32 or not api_key.isalnum():
            raise ValueError("FRED_API_KEY must be a 32-character alphanumeric string")
        self.api_key = api_key
        file_type_normalized = file_type.lower()
        if file_type_normalized not in {"json", "csv"}:
            raise ValueError("file_type must be either 'json' or 'csv'")
        self.file_type = file_type_normalized
        super().__init__(raw_root=raw_root, logger=logger, session=session)

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        params = {
            "series_id": symbol,
            "api_key": self.api_key,
            "file_type": self.file_type,
        }
        if start is not None:
            params["observation_start"] = start.date().strftime("%Y-%m-%d")
        return f"{self.BASE_URL}?{urlencode(params)}"

    def _download(self, url: str, *, session: requests.Session | None = None) -> str | bytes:
        active_session = session or self.session
        close_session = False
        if active_session is None:
            active_session = requests.Session()
            close_session = True
        try:
            for attempt in range(1, self.RETRIES + 1):
                response = active_session.get(url, headers=self.HEADERS, timeout=30)
                if response.ok:
                    if self.file_type == "csv":
                        return response.content
                    response.encoding = response.encoding or "utf-8"
                    return response.text
                if attempt == self.RETRIES:
                    response.raise_for_status()
                import time

                time.sleep(self.BACKOFF_SECONDS * attempt)
        finally:
            if close_session:
                active_session.close()
        raise RuntimeError(f"Unable to download from {url}")

    def parse(self, payload: str | bytes, symbol: str) -> pd.DataFrame:
        if self.file_type == "json":
            text = payload.decode("utf-8") if isinstance(payload, bytes | bytearray) else payload
            if text.lstrip().startswith("<"):
                msg = "FRED: non-CSV/non-JSON (rate limit?)"
                raise ValueError(msg)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                msg = "FRED: non-CSV/non-JSON (rate limit?)"
                raise ValueError(msg) from exc
            observations = data.get("observations", [])
            dates = [obs.get("date") for obs in observations]
            values = [obs.get("value") for obs in observations]
            frame = pd.DataFrame(
                {
                    "date": pd.to_datetime(dates, errors="coerce"),
                    "value": pd.to_numeric(values, errors="coerce"),
                    "symbol": symbol,
                }
            )
            frame = frame.dropna(subset=["date"]).reset_index(drop=True)
            frame["value"] = frame["value"].astype(float)
            return frame

        data_bytes = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        if data_bytes.lstrip().startswith(b"<"):
            msg = "FRED: non-CSV/non-JSON (rate limit?)"
            raise ValueError(msg)
        try:
            with ZipFile(io.BytesIO(data_bytes)) as archive:
                csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
                if not csv_names:
                    raise ValueError("FRED: CSV file not found in ZIP archive")
                with archive.open(csv_names[0]) as csv_file:
                    csv = pd.read_csv(csv_file)
        except (BadZipFile, UnicodeDecodeError) as exc:
            msg = "FRED: non-CSV/non-JSON (rate limit?)"
            raise ValueError(msg) from exc

        if csv.empty:
            return pd.DataFrame(columns=["date", "value", "symbol"])

        first_columns = list(csv.columns[:2])
        if len(first_columns) < 2:
            raise ValueError("FRED: unexpected CSV structure")
        csv = csv.rename(columns={first_columns[0]: "date", first_columns[1]: "value"})
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(csv["date"], errors="coerce"),
                "value": pd.to_numeric(csv["value"], errors="coerce"),
                "symbol": symbol,
            }
        )
        frame = frame.dropna(subset=["date"]).reset_index(drop=True)
        frame["value"] = frame["value"].astype(float)
        return frame
