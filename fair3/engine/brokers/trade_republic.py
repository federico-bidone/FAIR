"""Fetcher per il PDF dell'universo investibile di Trade Republic."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd
import pdfplumber
import requests

from .base import BaseBrokerFetcher, BrokerUniverseArtifact


@dataclass(frozen=True)
class TradeRepublicSection:
    """Rappresenta una sezione logica presente nel PDF di Trade Republic."""

    name: str
    asset_class: str


class TradeRepublicFetcher(BaseBrokerFetcher):
    """Scarica e interpreta l'universo investibile pubblicato da Trade Republic."""

    BROKER = "trade_republic"
    SOURCE_URL = "https://assets.traderepublic.com/assets/files/IT/Instrument_Universe_IT_en.pdf"
    LICENSE = "Trade Republic Terms"
    ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{10}\b")
    DEFAULT_SECTIONS: tuple[TradeRepublicSection, ...] = (
        TradeRepublicSection("Stocks", "Equity"),
        TradeRepublicSection("ETF", "ETF"),
        TradeRepublicSection("ETFs", "ETF"),
        TradeRepublicSection("ETNs", "ETN"),
        TradeRepublicSection("ETCs", "ETC"),
        TradeRepublicSection("Bonds", "Bond"),
        TradeRepublicSection("Funds", "Fund"),
        TradeRepublicSection("Crypto", "Crypto"),
    )

    def __init__(
        self,
        *,
        allowed_sections: Iterable[str] | None = None,
        session: requests.Session | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(session=session)
        self._url = url or self.SOURCE_URL
        if allowed_sections is None:
            self._allowed_sections: set[str] | None = None
        else:
            self._allowed_sections = {section.lower() for section in allowed_sections}

    def fetch_universe(self) -> BrokerUniverseArtifact:
        """Recupera il PDF, lo analizza e restituisce la tabella normalizzata.

        Returns:
            :class:`BrokerUniverseArtifact`: struttura con broker, dati tabellari
            e metadati utili a successive pipeline.
        """
        pdf_bytes = self._download_pdf(self._url)
        frame = self._parse_pdf(pdf_bytes)
        metadata = {
            "url": self._url,
            "license": self.LICENSE,
            "allowed_sections": None
            if self._allowed_sections is None
            else sorted(self._allowed_sections),
        }
        return BrokerUniverseArtifact(
            broker=self.BROKER,
            frame=frame,
            as_of=self._now(),
            metadata=metadata,
        )

    def _download_pdf(self, url: str) -> bytes:
        """Scarica il PDF dell'universo, con fallback GET se HEAD fallisce.

        Args:
            url: indirizzo pubblico del PDF.

        Returns:
            Contenuto binario del documento PDF.

        Raises:
            RuntimeError: se il payload ottenuto non è un PDF valido.
        """
        session = self._session or requests.Session()
        try:
            response = session.head(url, allow_redirects=True, timeout=15)
            if response.status_code >= 400:
                response.raise_for_status()
        except requests.RequestException:
            pass
        response = session.get(url, timeout=60)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
            raise RuntimeError("Downloaded payload is not a PDF document")
        return response.content

    def _parse_pdf(self, payload: bytes) -> pd.DataFrame:
        """Analizza riga per riga il PDF estraendo ISIN, nome e classificazioni.

        Args:
            payload: contenuto binario del PDF precedentemente scaricato.

        Returns:
            DataFrame con colonne ``isin``, ``name``, ``section`` e ``asset_class``
            ripulite e deduplicate.
        """
        instruments: list[dict[str, object]] = []
        allowed = self._allowed_sections
        section_map: Mapping[str, TradeRepublicSection] = {
            section.name.lower(): section for section in self.DEFAULT_SECTIONS
        }
        current_section: TradeRepublicSection | None = None
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                for raw_line in text.splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("TRADING UNIVERSE"):
                        continue
                    key = line.lower()
                    if key in section_map:
                        current_section = section_map[key]
                        continue
                    if line.startswith("ISIN") or set(line) == {"_"}:
                        continue
                    match = self.ISIN_RE.match(line)
                    if not match:
                        continue
                    if allowed is not None:
                        if current_section is None or current_section.name.lower() not in allowed:
                            continue
                    isin = match.group(0)
                    name = line[match.end() :].strip(" -–")
                    instruments.append(
                        {
                            "isin": isin,
                            "name": name,
                            "section": current_section.name if current_section else None,
                            "asset_class": current_section.asset_class if current_section else None,
                        }
                    )
        frame = pd.DataFrame(instruments, columns=["isin", "name", "section", "asset_class"])
        frame.drop_duplicates(subset=["isin"], inplace=True)
        frame.reset_index(drop=True, inplace=True)
        return frame


__all__ = ["TradeRepublicFetcher"]
