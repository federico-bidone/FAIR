"""Client leggero per l'API di mapping OpenFIGI."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Sequence

import requests

from .models import InstrumentListing


class OpenFIGIClient:
    """Incapsula le chiamate batch al servizio di mapping OpenFIGI."""

    BASE_URL = "https://api.openfigi.com/v3/mapping"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        session: requests.Session | None = None,
        batch_size: int = 100,
        max_retries: int = 5,
        initial_backoff: float = 2.0,
    ) -> None:
        self._api_key = api_key
        self._session = session or requests.Session()
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._initial_backoff = initial_backoff

    def map_isins(self, isins: Sequence[str]) -> dict[str, list[InstrumentListing]]:
        """Richiede a OpenFIGI i listing associati agli ISIN forniti.

        Args:
            isins: sequenza di codici ISIN da mappare.

        Returns:
            Dizionario ``ISIN -> elenco di InstrumentListing`` deduplicato.

        Raises:
            RuntimeError: se viene superato il limite di rate limiting del servizio.
        """
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-OPENFIGI-APIKEY"] = self._api_key
        unique_isins = list(dict.fromkeys(isins))
        mapping: dict[str, list[InstrumentListing]] = defaultdict(list)
        for start in range(0, len(unique_isins), self._batch_size):
            batch = unique_isins[start : start + self._batch_size]
            payload = [{"idType": "ID_ISIN", "idValue": value} for value in batch]
            attempt = 0
            backoff = self._initial_backoff
            while True:
                response = self._session.post(
                    self.BASE_URL, json=payload, headers=headers, timeout=60
                )
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after is not None else backoff
                    time.sleep(delay)
                    attempt += 1
                    backoff = min(backoff * 2, 60)
                    if attempt > self._max_retries:
                        raise RuntimeError("OpenFIGI rate limit exceeded")
                    continue
                try:
                    response.raise_for_status()
                except requests.RequestException:  # pragma: no cover - network failure
                    attempt += 1
                    if attempt > self._max_retries:
                        raise
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                results = response.json()
                for request_payload, result_payload in zip(payload, results, strict=False):
                    isin = request_payload["idValue"]
                    for entry in (result_payload or {}).get("data", []) or []:
                        mapping[isin].append(
                            InstrumentListing(
                                isin=isin,
                                ticker=entry.get("ticker"),
                                mic=entry.get("micCode"),
                                currency=entry.get("currency"),
                                exchange=entry.get("exchDesc"),
                                exch_code=entry.get("exchCode"),
                            )
                        )
                break
        return mapping


__all__ = ["OpenFIGIClient"]
