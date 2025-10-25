from __future__ import annotations

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["ECBFetcher"]


class ECBFetcher(BaseCSVFetcher):
    """Scarica i cambi ufficiali BCE convertendoli nello schema FAIR canonico."""

    SOURCE = "ecb"
    LICENSE = "European Central Bank (ECB) Statistical Data Warehouse Terms of Use"
    BASE_URL = "https://data-api.ecb.europa.eu/service/data/EXR"
    DEFAULT_SYMBOLS = ("USD", "GBP")

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Compone l'URL EXR con filtri opzionali sulla data iniziale."""
        series = f"D.{symbol}.EUR.SP00.A"
        params: list[str] = ["format=csvdata"]
        if start is not None:
            params.append(f"startPeriod={start.date():%Y-%m-%d}")
        query = "&".join(params)
        return f"{self.BASE_URL}/{series}?{query}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Normalizza il CSV EXR e forza i valori numerici a float espliciti."""
        frame = self._simple_frame(
            payload,
            symbol,
            date_column="TIME_PERIOD",
            value_column="OBS_VALUE",
        )
        frame["value"] = frame["value"].astype(float)
        return frame
