"""Fetcher for Kenneth R. French Data Library archives."""

from __future__ import annotations

import io
import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from zipfile import BadZipFile, ZipFile

import pandas as pd
import requests

from .registry import BaseCSVFetcher

__all__ = ["FrenchFetcher", "FrenchDataset"]


@dataclass(frozen=True, slots=True)
class FrenchDataset:
    """Declarative metadata describing a Kenneth French dataset archive.

    Attributes:
        filename: Name of the ZIP archive to download from the French library.
        columns: Ordered collection of factor columns to keep; ``None`` triggers
            header inference.
        value_scale: Scalar applied to raw values (defaults to converting percent
            figures into decimal returns).
        missing_sentinels: Numeric placeholders that should be treated as
            missing observations.
        inner: Optional explicit member name to extract from the ZIP payload.
    """

    filename: str
    columns: Sequence[str] | None
    value_scale: float = 0.01
    missing_sentinels: Sequence[float] = (-99.99, -999.0, -999.99)
    inner: str | None = None


class FrenchFetcher(BaseCSVFetcher):
    """Download and normalise Kenneth R. French Data Library archives.

    Attributes:
        DATASETS: Declarative mapping between logical symbols and archive
            descriptors.
        DEFAULT_SYMBOLS: Tuple returned when callers omit an explicit symbol
            selection.
    """

    SOURCE: Final[str] = "french"
    LICENSE: Final[str] = "Kenneth R. French Data Library (for educational use)"
    BASE_URL: Final[str] = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
    DATASETS: Final[dict[str, FrenchDataset]] = {
        "research_factors_monthly": FrenchDataset(
            filename="F-F_Research_Data_Factors_TXT.zip",
            columns=("Mkt-RF", "SMB", "HML", "RF"),
        ),
        "five_factors_2x3": FrenchDataset(
            filename="F-F_Research_Data_5_Factors_2x3_TXT.zip",
            columns=("Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"),
        ),
        "momentum": FrenchDataset(
            filename="F-F_Momentum_Factor_TXT.zip",
            columns=("Mom",),
        ),
        "industry_49": FrenchDataset(
            filename="49_Industry_Portfolios_TXT.zip",
            columns=None,
        ),
    }
    DEFAULT_SYMBOLS: Final[tuple[str, ...]] = tuple(DATASETS.keys())

    def __init__(
        self,
        *,
        raw_root: Path | str | None = None,
        logger: logging.Logger | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """Initialise the fetcher with optional storage and logging overrides."""

        super().__init__(raw_root=raw_root, logger=logger, session=session)

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Compose the download URL for the requested dataset symbol."""

        dataset = self._get_dataset(symbol)
        return f"{self.BASE_URL}/{dataset.filename}"

    def _download(
        self,
        url: str,
        *,
        session: requests.Session | None = None,
    ) -> bytes:
        """Download the ZIP archive returning the raw payload bytes."""

        active_session = session or self.session
        close_session = False
        if active_session is None:
            active_session = requests.Session()
            close_session = True
        try:
            for attempt in range(1, self.RETRIES + 1):
                response = active_session.get(url, headers=self.HEADERS, timeout=30)
                if response.ok:
                    return response.content
                if attempt == self.RETRIES:
                    response.raise_for_status()
                time.sleep(self.BACKOFF_SECONDS * attempt)
        finally:
            if close_session:
                active_session.close()
        raise RuntimeError(f"Unable to download from {url}")

    def parse(self, payload: bytes | str, symbol: str) -> pd.DataFrame:
        """Convert the ZIP payload into the FAIR canonical ingest frame.

        Args:
            payload: Raw bytes (or UTF-8 text) representing the downloaded
                archive.
            symbol: Logical dataset identifier supplied by the caller.

        Returns:
            DataFrame with columns ``date``, ``value`` and ``symbol`` ready for
            the ingest pipeline.

        Raises:
            ValueError: If the payload is HTML, corrupted, or does not expose a
                tabular section compatible with the dataset definition.
        """

        dataset = self._get_dataset(symbol)
        raw_bytes = payload if isinstance(payload, bytes | bytearray) else payload.encode("utf-8")
        if raw_bytes.lstrip().startswith(b"<"):
            raise ValueError("French: HTML payload detected (likely rate limited)")
        try:
            with ZipFile(io.BytesIO(raw_bytes)) as archive:
                member_name = dataset.inner or self._select_member_name(archive)
                with archive.open(member_name) as handle:
                    text = handle.read().decode("latin-1")
        except (BadZipFile, KeyError, UnicodeDecodeError) as exc:
            raise ValueError("French: invalid ZIP payload") from exc
        frame = self._parse_text(text, symbol, dataset)
        return frame

    def _get_dataset(self, symbol: str) -> FrenchDataset:
        try:
            return self.DATASETS[symbol]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported French dataset: {symbol}") from exc

    def _select_member_name(self, archive: ZipFile) -> str:
        """Return a deterministic member name from the archive contents."""

        candidates = [name for name in archive.namelist() if not name.endswith("/")]
        if not candidates:
            raise ValueError("French: ZIP archive is empty")
        candidates.sort()
        return candidates[0]

    def _parse_text(
        self,
        text: str,
        symbol: str,
        dataset: FrenchDataset,
    ) -> pd.DataFrame:
        """Parse the textual body of a French dataset into a normalised frame."""

        lines = text.splitlines()
        data_lines: list[list[str]] = []
        tokens_header: Sequence[str] | None = dataset.columns
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if data_lines:
                    break
                continue
            if stripped[0].isdigit():
                tokens = stripped.replace(",", " ").split()
                if tokens_header is None:
                    tokens_header = self._infer_header(lines, len(tokens))
                expected_length = 1 + len(tokens_header)
                if len(tokens) < expected_length:
                    continue
                data_lines.append(tokens[:expected_length])
                continue
            if data_lines:
                break
        if not data_lines or tokens_header is None:
            raise ValueError("French: tabular section not found in payload")
        frame = self._assemble_frame(data_lines, tokens_header)
        melted = frame.melt(id_vars="date", var_name="factor", value_name="value")
        if dataset.missing_sentinels:
            melted.loc[melted["value"].isin(dataset.missing_sentinels), "value"] = pd.NA
        melted["value"] = pd.to_numeric(melted["value"], errors="coerce")
        melted = melted.dropna(subset=["date", "value"]).reset_index(drop=True)
        melted["value"] = melted["value"].astype(float) * dataset.value_scale
        melted["symbol"] = [
            f"{symbol}_{self._normalise_factor_name(factor)}" for factor in melted["factor"]
        ]
        return melted[["date", "value", "symbol"]]

    def _infer_header(self, lines: Sequence[str], token_count: int) -> Sequence[str]:
        """Infer factor headers when the dataset definition does not provide them."""

        for raw_line in reversed(lines):
            stripped = raw_line.strip()
            if not stripped or stripped[0].isdigit():
                continue
            tokens = stripped.replace(",", " ").split()
            if len(tokens) in {token_count, token_count - 1}:
                if len(tokens) == token_count:
                    return tokens[1:]
                return tokens
        return [f"col_{index:02d}" for index in range(1, token_count)]

    def _assemble_frame(
        self,
        data_lines: Iterable[list[str]],
        header_tokens: Sequence[str],
    ) -> pd.DataFrame:
        """Assemble a rectangular DataFrame from tokenised rows."""

        dates: list[pd.Timestamp] = []
        values: dict[str, list[str]] = {token: [] for token in header_tokens}
        for tokens in data_lines:
            date_token = tokens[0]
            parsed_date = self._parse_date(date_token)
            if pd.isna(parsed_date):
                continue
            value_tokens = tokens[1 : 1 + len(header_tokens)]
            dates.append(parsed_date)
            for key, value in zip(header_tokens, value_tokens, strict=False):
                values[key].append(value)
        if not dates:
            raise ValueError("French: no valid observations in payload")
        frame_dict = {"date": dates}
        for key, series in values.items():
            frame_dict[key] = series
        return pd.DataFrame(frame_dict)

    def _parse_date(self, token: str) -> pd.Timestamp:
        """Parse YYYYMM or YYYY date tokens into pandas timestamps."""

        parsed = pd.to_datetime(token, format="%Y%m", errors="coerce")
        if pd.isna(parsed):
            parsed = pd.to_datetime(token, format="%Y", errors="coerce")
        return parsed

    def _normalise_factor_name(self, name: str) -> str:
        """Normalise factor labels into lower-case snake-case identifiers."""

        lowered = name.strip().lower()
        sanitized = "".join(character if character.isalnum() else "_" for character in lowered)
        while "__" in sanitized:
            sanitized = sanitized.replace("__", "_")
        return sanitized.strip("_") or "value"
