"""Test mirati alle utility di registry dell'ingest con spiegazioni in italiano."""

from __future__ import annotations

from datetime import UTC, date, datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from fair3.engine.ingest import registry
from fair3.engine.ingest.registry import BaseCSVFetcher, run_ingest


class DummyFetcher(BaseCSVFetcher):
    """Fetcher di test che simula il download tramite payload in memoria."""

    SOURCE = "dummy"
    LICENSE = "Licenza fittizia"
    BASE_URL = "https://example.invalid/dummy"
    DEFAULT_SYMBOLS = ("AAA", "BBB")

    def __init__(self, *, payloads: dict[str, str], **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._payloads = payloads
        self.request_log: list[tuple[str, str | None]] = []

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Registra la richiesta così da poterla ispezionare nei test."""
        start_marker = None if start is None else start.isoformat()
        self.request_log.append((symbol, start_marker))
        return f"{self.BASE_URL}/{symbol}"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:
        """Converte il CSV in DataFrame usando lo schema canonico FAIR."""
        csv = pd.read_csv(StringIO(payload))
        return (
            pd.DataFrame(
                {
                    "date": pd.to_datetime(csv["date"], errors="coerce"),
                    "value": pd.to_numeric(csv["value"], errors="coerce"),
                    "symbol": symbol,
                }
            )
            .dropna(subset=["date"])
            .reset_index(drop=True)
        )


def _sample_payload(value: float, *, date: str = "2024-01-01") -> str:
    """Costruisce una riga CSV minima compatibile con DummyFetcher."""

    return f"date,value\n{date},{value}\n"


def test_fetch_filtra_date_e_costruisce_metadati(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifica che `fetch` applichi il filtro `start` e popoli i metadati audit."""

    payloads = {"AAA": _sample_payload(1.0, date="2023-12-31"), "BBB": _sample_payload(2.5)}
    fetcher = DummyFetcher(payloads=payloads, raw_root=tmp_path)
    monkeypatch.setattr(
        fetcher,
        "_download",
        lambda url, session=None: fetcher._payloads[url.split("/")[-1]],
    )
    artifact = fetcher.fetch(symbols=["AAA", "BBB"], start=date(2024, 1, 1))

    # Solo BBB sopravvive al filtro start; ci aspettiamo un'unica riga.
    assert artifact.data["symbol"].tolist() == ["BBB"]
    assert pytest.approx(artifact.data.loc[0, "value"], rel=1e-9) == 2.5

    # I metadati devono tracciare licenza, start filtrato e URL richiesti.
    assert artifact.metadata["license"] == DummyFetcher.LICENSE
    assert artifact.metadata["start"].startswith("2024-01-01")
    assert [entry["symbol"] for entry in artifact.metadata["requests"]] == ["AAA", "BBB"]

    # Il CSV serializzato deve rispettare naming e formattazione FAIR (YYYY-MM-DD).
    written = artifact.path.read_text().strip().splitlines()
    assert written[0] == "date,value,symbol"
    assert written[-1].endswith(",BBB")


def test_fetch_con_progress_attiva_tqdm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Quando progress=True il fetcher deve invocare tqdm con descrizione coerente."""

    payloads = {"AAA": _sample_payload(1.0)}
    fetcher = DummyFetcher(payloads=payloads, raw_root=tmp_path)
    monkeypatch.setattr(
        fetcher,
        "_download",
        lambda url, session=None: fetcher._payloads[url.split("/")[-1]],
    )

    captured: dict[str, object] = {}

    def fake_tqdm(iterable: list[str], **kwargs: object) -> list[str]:
        captured.update(kwargs)
        return iterable

    monkeypatch.setattr(registry, "tqdm", fake_tqdm)
    fetcher.fetch(symbols=["AAA"], progress=True)

    assert captured["disable"] is False
    assert captured["desc"] == "ingest:dummy"
    assert captured["unit"] == "symbol"


def test_fetch_richiede_almeno_un_simbolo(tmp_path: Path) -> None:
    """Lancia un errore chiaro quando la lista dei simboli è vuota."""

    fetcher = DummyFetcher(payloads={}, raw_root=tmp_path)
    with pytest.raises(ValueError, match="At least one symbol must be provided"):
        fetcher.fetch(symbols=[])


def test_simple_frame_rileva_colonne_mancanti(tmp_path: Path) -> None:
    """`_simple_frame` deve fallire se il CSV non espone le colonne attese."""

    fetcher = DummyFetcher(payloads={}, raw_root=tmp_path)
    payload = "date,valore\n2024-01-01,1.0\n"
    with pytest.raises(ValueError, match="Expected columns"):
        fetcher._simple_frame(payload, "AAA", date_column="date", value_column="value")


def test_download_apre_sessione_e_la_chiude(monkeypatch: pytest.MonkeyPatch) -> None:
    """Il metodo `_download` deve chiudere la sessione creata internamente."""

    calls: list[str] = []
    created_sessions: list[FakeSession] = []

    class FakeResponse:
        def __init__(self) -> None:
            self.ok = True
            self.text = "payload"
            self.encoding = None

        def raise_for_status(self) -> None:  # pragma: no cover - non invocato in scenario ok
            raise AssertionError("Non dovremmo arrivare qui")

    class FakeSession:
        def __init__(self) -> None:
            self.closed = False

        def get(self, url: str, headers: dict[str, str], timeout: int) -> FakeResponse:
            calls.append(url)
            return FakeResponse()

        def close(self) -> None:
            self.closed = True

    def factory() -> FakeSession:
        session = FakeSession()
        created_sessions.append(session)
        return session

    monkeypatch.setattr(registry.requests, "Session", factory)
    fetcher = DummyFetcher(payloads={})
    result = fetcher._download("https://example.invalid/test")

    assert result == "payload"
    assert calls == ["https://example.invalid/test"]
    assert created_sessions and created_sessions[0].closed


def test_run_ingest_delega_ai_fetcher(monkeypatch: pytest.MonkeyPatch) -> None:
    """`run_ingest` deve creare il fetcher e inoltrare i parametri senza modificarli."""

    captured: dict[str, object] = {}

    class FakeFetcher:
        def fetch(
            self,
            *,
            symbols: object,
            start: object,
            as_of: object,
            progress: bool,
        ) -> str:
            captured.update(
                {
                    "symbols": symbols,
                    "start": start,
                    "as_of": as_of,
                    "progress": progress,
                }
            )
            return "ok"

    monkeypatch.setattr(registry, "create_fetcher", lambda source, raw_root=None: FakeFetcher())

    result = run_ingest(
        "dummy",
        symbols=["X"],
        start=datetime(2023, 12, 31, tzinfo=UTC),
        raw_root=Path("/tmp"),
        as_of=datetime(2024, 1, 1, tzinfo=UTC),
        progress=True,
    )

    assert result == "ok"
    assert captured["symbols"] == ["X"]
    assert captured["start"].isoformat().startswith("2023-12-31")
    assert captured["as_of"].isoformat().startswith("2024-01-01")
    assert captured["progress"] is True
