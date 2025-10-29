"""Fetcher manuale per dataset Curvo.eu con conversione EUR e total return.

Il fetcher legge CSV posizionati in ``data/curvo/`` con colonne ``date`` (o
``Date``), ``price`` e ``dividend`` (dividendi/cedole facoltativi) più un campo
``currency`` opzionale. Per le valute diverse dall'euro è necessario fornire un
file BCE ``data/curvo/fx/<CCY>_EUR.csv`` con colonne ``date``/``rate`` (tasso
1 unità valuta → EUR). I prezzi e i dividendi vengono convertiti in EUR,
reinvestiti e restituiti come serie total return normalizzate (colonne FAIR
``date``, ``value``, ``symbol``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

import pandas as pd

from .registry import BaseCSVFetcher, IngestArtifact

__all__ = ["CurvoInstrumentSpec", "CurvoFetcher"]


@dataclass(frozen=True)
class CurvoInstrumentSpec:
    """Descrive un dataset manuale Curvo.eu e il simbolo FAIR da esporre.

    Attributes:
        symbol: Nome del simbolo esposto dal fetcher (es. ``CURVO_MSCI_WORLD_NET_TR``).
        filename: Nome del file CSV posizionato nella directory manuale.
        currency: Valuta del prezzo/dividendo nel file sorgente.
        date_column: Colonna che contiene le date delle osservazioni.
        price_column: Colonna con il prezzo dell'indice o ETF.
        dividend_column: Colonna con dividendi/cedole da reinvestire (``None`` se assente).
        currency_column: Colonna opzionale che indica la valuta (se diversa da ``currency``).
        tz: Identificatore timezone della serie (usato per metadati).
    """

    symbol: str
    filename: str
    currency: str = "EUR"
    date_column: str = "date"
    price_column: str = "price"
    dividend_column: str | None = "dividend"
    currency_column: str | None = None
    tz: str = "Europe/Rome"


DEFAULT_CURVO_SPECS: Final[tuple[CurvoInstrumentSpec, ...]] = (
    CurvoInstrumentSpec(
        symbol="CURVO_MSCI_WORLD_NET_TR",
        filename="msci_world_net.csv",
        currency="USD",
        date_column="Date",
        price_column="Price",
        dividend_column="Dividend",
    ),
    CurvoInstrumentSpec(
        symbol="CURVO_MSCI_EMU_NET_TR",
        filename="msci_emu_net.csv",
        currency="EUR",
        date_column="Date",
        price_column="Price",
        dividend_column="Dividend",
    ),
    CurvoInstrumentSpec(
        symbol="CURVO_GLOBAL_AGG_EUR_TR",
        filename="bloomberg_global_agg_eur.csv",
        currency="EUR",
        date_column="Date",
        price_column="Price",
        dividend_column="Coupon",
    ),
)


class CurvoFetcher(BaseCSVFetcher):
    """Fetcher manuale che armonizza i dataset Curvo.eu in EUR con total return.

    Attributes:
        manual_root: Directory che ospita i CSV scaricati manualmente.
        fx_root: Directory che ospita i file FX BCE necessari per la conversione.
        _spec_index: Dizionario che mappa simbolo → configurazione del dataset.
    """

    SOURCE = "curvo"
    LICENSE = "Curvo.eu plus underlying MSCI/FTSE/STOXX/ICE indices — informational use"
    BASE_URL = "https://curvo.eu/data"
    DEFAULT_SYMBOLS: Final[tuple[str, ...]] = tuple(spec.symbol for spec in DEFAULT_CURVO_SPECS)

    def __init__(
        self,
        *,
        manual_root: Path | str | None = None,
        fx_root: Path | str | None = None,
        instrument_specs: Iterable[CurvoInstrumentSpec] | None = None,
        raw_root: Path | str | None = None,
        **kwargs: object,
    ) -> None:
        """Inizializza il fetcher manuale con directory e specifiche personalizzate.

        Args:
            manual_root: Directory che contiene i CSV scaricati dalle fonti Curvo.
            fx_root: Directory che contiene i CSV FX BCE ``<Ccy>_EUR.csv``.
            instrument_specs: Collezione di specifiche manuali (default predefiniti).
            raw_root: Directory dove salvare il CSV normalizzato generato.
            **kwargs: Parametri aggiuntivi propagati alla superclasse.

        Raises:
            ValueError: Se non viene fornita alcuna specifica di strumento.
        """
        super().__init__(raw_root=raw_root, **kwargs)
        self.manual_root = Path(manual_root) if manual_root is not None else Path("data") / "curvo"
        self.fx_root = Path(fx_root) if fx_root is not None else self.manual_root / "fx"
        specs = tuple(instrument_specs) if instrument_specs is not None else DEFAULT_CURVO_SPECS
        if not specs:
            raise ValueError("At least one instrument spec must be provided for CurvoFetcher")
        self._spec_index: Mapping[str, CurvoInstrumentSpec] = {spec.symbol: spec for spec in specs}

    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: date | datetime | None = None,
        as_of: datetime | None = None,
        progress: bool = False,
        session: object | None = None,
    ) -> IngestArtifact:
        """Carica i dataset Curvo richiesti e restituisce un artefatto FAIR.

        Args:
            symbols: Lista di simboli Curvo da importare (default tutti quelli configurati).
            start: Data minima (inclusiva) per filtrare le osservazioni.
            as_of: Timestamp usato per nominare l'artefatto prodotto.
            progress: Argomento richiesto dalla superclasse; ignorato qui.
            session: Argomento richiesto dalla superclasse; ignorato qui.

        Returns:
            Artefatto di ingest con DataFrame ``date/value/symbol`` e metadati di audit.
        """
        del progress, session
        requested = self._resolve_symbols(symbols)
        timestamp = as_of or datetime.now(UTC)
        start_ts = pd.to_datetime(start) if start is not None else None
        frames: list[pd.DataFrame] = []
        requests_meta: list[MutableMapping[str, object]] = []
        for symbol in requested:
            spec = self._spec_index[symbol]
            dataset, currency = self._load_instrument(spec)
            if start_ts is not None:
                dataset = dataset[dataset["date"] >= start_ts]
            dataset = dataset.sort_values("date").reset_index(drop=True)
            frames.append(dataset.assign(symbol=symbol))
            requests_meta.append(self._build_metadata_entry(spec, len(dataset), currency))
            self.logger.info(
                "ingest_complete source=%s symbol=%s rows=%d license=%s manual=%s",
                self.SOURCE,
                symbol,
                len(dataset),
                self.LICENSE,
                self.manual_root / spec.filename,
            )
        combined = (
            pd.concat(frames, ignore_index=True)
            if frames
            else pd.DataFrame(columns=["date", "value", "symbol"])
        )
        path = self._write_csv(combined, timestamp)
        metadata: MutableMapping[str, object] = {
            "license": self.LICENSE,
            "as_of": timestamp.isoformat(),
            "requests": requests_meta,
            "start": start_ts.isoformat() if start_ts is not None else None,
        }
        return IngestArtifact(
            source=self.SOURCE,
            path=path,
            data=combined,
            metadata=metadata,
        )

    def _resolve_symbols(self, symbols: Iterable[str] | None) -> list[str]:
        """Valida e restituisce la lista di simboli richiesti dal chiamante.

        Args:
            symbols: Sequenza opzionale di simboli richiesti.

        Returns:
            Lista di simboli pronta per l'elaborazione.

        Raises:
            ValueError: Se la lista è vuota o contiene simboli sconosciuti.
        """
        if symbols is None:
            requested = sorted(self._spec_index)
        else:
            requested = [str(symbol) for symbol in symbols]
        if not requested:
            raise ValueError("At least one symbol must be provided")
        missing = [symbol for symbol in requested if symbol not in self._spec_index]
        if missing:
            missing_fmt = ", ".join(sorted(missing))
            raise ValueError(f"Unknown Curvo symbols: {missing_fmt}")
        return requested

    def _load_instrument(self, spec: CurvoInstrumentSpec) -> tuple[pd.DataFrame, str]:
        """Carica e normalizza il dataset relativo a uno specifico simbolo Curvo.

        Args:
            spec: Configurazione dichiarativa del dataset da elaborare.

        Returns:
            Tuple con il DataFrame ``date``/``value`` (total return EUR) e la
            valuta effettivamente utilizzata per la conversione.

        Raises:
            FileNotFoundError: Se il CSV manuale non è presente.
            ValueError: Se mancano colonne obbligatorie o la serie FX è incompleta.
        """
        csv_path = self.manual_root / spec.filename
        if not csv_path.exists():
            msg = (
                "Manual Curvo dataset missing. Download the CSV from Curvo's data sources "
                f"and place it at {csv_path}."
            )
            raise FileNotFoundError(msg)
        frame = pd.read_csv(csv_path)
        if spec.date_column not in frame.columns:
            raise ValueError(
                f"Curvo dataset {spec.filename} is missing date column '{spec.date_column}'"
            )
        if spec.price_column not in frame.columns:
            raise ValueError(
                f"Curvo dataset {spec.filename} is missing price column '{spec.price_column}'"
            )
        dates = pd.to_datetime(frame[spec.date_column], errors="coerce")
        prices = pd.to_numeric(frame[spec.price_column], errors="coerce")
        if spec.dividend_column:
            dividend_raw = pd.to_numeric(frame[spec.dividend_column], errors="coerce").fillna(0.0)
        else:
            dividend_raw = pd.Series(0.0, index=frame.index, dtype="float64")
        data = (
            pd.DataFrame(
                {
                    "date": dates,
                    "price": prices,
                    "dividend": dividend_raw,
                }
            )
            .dropna(subset=["date", "price"])
            .sort_values("date")
            .reset_index(drop=True)
        )
        currency = self._resolve_currency(frame, spec)
        fx_series = self._fx_series(currency)
        if fx_series.empty:
            fx_values = pd.Series(1.0, index=data.index, dtype="float64")
        else:
            fx_lookup = fx_series.reindex(pd.DatetimeIndex(data["date"])).ffill()
            if fx_lookup.isna().any():
                msg = (
                    "FX series lacks coverage for some Curvo observations; ensure ECB FX "
                    "CSV includes all dates."
                )
                raise ValueError(msg)
            fx_values = pd.Series(fx_lookup.to_numpy(), index=data.index, dtype="float64")
        price_eur = data["price"].to_numpy() * fx_values.to_numpy()
        dividend_eur = data["dividend"].to_numpy() * fx_values.to_numpy()
        total_return = self._total_return_index(
            pd.Series(price_eur, index=data.index, dtype="float64"),
            pd.Series(dividend_eur, index=data.index, dtype="float64"),
        )
        tidy = pd.DataFrame(
            {
                "date": data["date"],
                "value": total_return,
            }
        ).dropna(subset=["date", "value"])
        return tidy.reset_index(drop=True), currency

    def _resolve_currency(self, frame: pd.DataFrame, spec: CurvoInstrumentSpec) -> str:
        """Determina la valuta da utilizzare per la conversione EUR.

        Args:
            frame: DataFrame sorgente letto dal CSV manuale.
            spec: Configurazione del dataset.

        Returns:
            Stringa con il codice valuta ISO (es. ``USD``).

        Raises:
            ValueError: Se nel file compaiono più valute diverse.
        """
        if spec.currency_column and spec.currency_column in frame.columns:
            series = frame[spec.currency_column].astype(str).str.upper()
            currencies = series.dropna().unique()
            if len(currencies) > 1:
                raise ValueError(
                    "Curvo dataset exposes multiple currencies; split files per currency."
                )
            return currencies[0] if len(currencies) == 1 else spec.currency.upper()
        return spec.currency.upper()

    def _fx_series(self, currency: str) -> pd.Series:
        """Carica la serie FX BCE necessaria per convertire in EUR.

        Args:
            currency: Codice ISO della valuta di partenza.

        Returns:
            Serie pandas indicizzata per data con il tasso ``currency→EUR``.

        Raises:
            FileNotFoundError: Se il file FX richiesto non è presente.
            ValueError: Se il CSV non espone colonne ``date``/``rate``.
        """
        if currency.upper() == "EUR":
            return pd.Series(1.0, index=pd.Index([], dtype="datetime64[ns]"))
        fx_path = self.fx_root / f"{currency.upper()}_EUR.csv"
        if not fx_path.exists():
            msg = (
                "Missing ECB FX CSV for currency conversion. Place a file named "
                f"{fx_path.name} under {fx_path.parent}."
            )
            raise FileNotFoundError(msg)
        fx_frame = pd.read_csv(fx_path)
        if "date" not in fx_frame.columns or "rate" not in fx_frame.columns:
            raise ValueError(
                f"FX CSV {fx_path.name} must expose 'date' and 'rate' columns to convert Curvo data"
            )
        dates = pd.to_datetime(fx_frame["date"], errors="coerce")
        rates = pd.to_numeric(fx_frame["rate"], errors="coerce")
        mask = dates.notna() & rates.notna()
        series = pd.Series(rates[mask].to_numpy(), index=dates[mask]).dropna()
        return series.sort_index()

    def _total_return_index(self, price_eur: pd.Series, dividend_eur: pd.Series) -> pd.Series:
        """Calcola l'indice total return reinvestendo dividendi in EUR.

        Args:
            price_eur: Serie di prezzi convertiti in EUR.
            dividend_eur: Serie di dividendi/cedole convertiti in EUR.

        Returns:
            Serie di valori total return con lo stesso indice di ``price_eur``.
        """
        aligned = price_eur.copy()
        aligned = aligned.ffill()
        prev = aligned.shift(1)
        dividend = dividend_eur.fillna(0.0)
        returns = (aligned - prev + dividend) / prev
        returns = returns.fillna(0.0)
        if aligned.empty:
            return aligned
        base = aligned.iloc[0]
        total = base * (1.0 + returns).cumprod()
        return total

    def _build_metadata_entry(
        self, spec: CurvoInstrumentSpec, rows: int, currency: str
    ) -> MutableMapping[str, object]:
        """Costruisce l'entry di metadati per un simbolo Curvo specifico.

        Args:
            spec: Configurazione del simbolo.
            rows: Numero di osservazioni prodotte dopo il filtro start.
            currency: Valuta usata per la conversione (post eventuale colonna).

        Returns:
            Dizionario con percorso manuale, valuta, timezone e file FX (se usato).
        """
        entry: MutableMapping[str, object] = {
            "symbol": spec.symbol,
            "file": str(self.manual_root / spec.filename),
            "currency": currency,
            "rows": rows,
        }
        if currency.upper() != "EUR":
            entry["fx_file"] = str(self.fx_root / f"{currency.upper()}_EUR.csv")
        entry["tz"] = spec.tz
        return entry
