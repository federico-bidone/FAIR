"""Fetcher LBMA per i fixing delle 15:00 London su oro e argento."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime
from html.parser import HTMLParser

import pandas as pd

from .registry import BaseCSVFetcher

__all__ = ["LBMAFetcher"]


@dataclass(frozen=True)
class MetalSpec:
    """Metadati dichiarativi per una serie LBMA supportata.

    Attributes:
        path: Porzione di URL relativa alla pagina che espone la tabella.
        value_column: Nome della colonna che contiene il fixing in USD.
    """

    path: str
    value_column: str


SERIES: Mapping[str, MetalSpec] = {
    "gold_pm": MetalSpec(
        path="gold-prices#/,pm",  # riferimento informativo sulla pagina LBMA
        value_column="USD (PM)",
    ),
    "silver_pm": MetalSpec(
        path="silver-prices#/,pm",
        value_column="USD (PM)",
    ),
}


class LBMAFetcher(BaseCSVFetcher):
    """Scarica e normalizza i fixing delle 15:00 London per oro e argento.

    Il fetcher utilizza le tabelle HTML pubblicate da LBMA, converte i prezzi da USD
    a EUR tramite i cambi BCE e aggiunge ``pit_flag`` quando l'osservazione coincide
    con le 16:00 CET.
    """

    SOURCE = "lbma"
    LICENSE = "LBMA precious metal prices — informational use only"
    BASE_URL = "https://www.lbma.org.uk/prices-and-data"
    DEFAULT_SYMBOLS = tuple(SERIES.keys())

    FX_SERIES = "USD"

    def __init__(
        self,
        *,
        fx_rates: Mapping[str | datetime | date_type, float] | pd.Series | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._fx_cache: dict[date_type, float] = {}
        if fx_rates is not None:
            self._fx_cache.update(self._normalise_fx_rates(fx_rates))

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:
        """Restituisce l'URL della tabella HTML per il metallo richiesto.

        Args:
            symbol: Identificatore della serie LBMA (``gold_pm`` o ``silver_pm``).
            start: Data minima richiesta; non usata poiché il feed è giornaliero.

        Returns:
            URL completo verso la pagina HTML da cui estrarre i prezzi.

        Raises:
            ValueError: Se viene richiesto un simbolo non supportato.
        """

        spec = self._resolve_spec(symbol)
        return f"{self.BASE_URL}/{spec.path}"

    def parse(self, payload: str | bytes, symbol: str) -> pd.DataFrame:
        """Interpreta la tabella HTML LBMA e converte i prezzi in EUR.

        Args:
            payload: HTML contenente almeno una tabella con colonne ``Date`` e
                ``USD (PM)``.
            symbol: Nome della serie LBMA richiesta.

        Returns:
            DataFrame con colonne ``date`` (UTC), ``value`` (EUR), ``symbol``,
            ``currency`` (sempre EUR) e ``pit_flag``.

        Raises:
            ValueError: Se il payload non contiene una tabella valida oppure se
                mancano i cambi necessari alla conversione in EUR.
        """

        if isinstance(payload, bytes):
            text = payload.decode("utf-8", errors="ignore")
        else:
            text = payload
        if text.lstrip().startswith("<") and "<table" not in text.lower():
            msg = "LBMA payload appears to be HTML without data"
            raise ValueError(msg)

        tables = self._parse_tables(text)
        if not tables:
            msg = "Unable to locate LBMA data table in payload"
            raise ValueError(msg)
        frame = self._select_table_with_date(tables)

        spec = self._resolve_spec(symbol)
        columns = {col: col.strip() for col in frame.columns}
        frame = frame.rename(columns=columns)
        if "Date" not in frame.columns or spec.value_column not in frame.columns:
            msg = (
                "Expected columns 'Date' and " f"'{spec.value_column}' in LBMA payload for {symbol}"
            )
            raise ValueError(msg)

        dates = pd.to_datetime(frame["Date"], errors="coerce", dayfirst=True)
        dates = dates + pd.Timedelta(hours=15)
        dates = dates.dt.tz_localize(
            "Europe/London",
            nonexistent="NaT",
            ambiguous="NaT",
        )
        rome_times = dates.dt.tz_convert("Europe/Rome")
        pit_flag = (rome_times.dt.hour == 16).astype("int8")
        utc_times = rome_times.dt.tz_convert("UTC").dt.tz_localize(None)

        usd_prices = pd.to_numeric(frame[spec.value_column], errors="coerce")
        fx_rates = self._fx_rates_for_dates(rome_times)
        eur_prices = usd_prices * fx_rates

        result = pd.DataFrame(
            {
                "date": utc_times,
                "value": eur_prices,
                "symbol": symbol,
                "currency": "EUR",
                "pit_flag": pit_flag,
            }
        )
        result = result.dropna(subset=["date", "value"]).reset_index(drop=True)
        return result

    def _select_table_with_date(self, tables: list[pd.DataFrame]) -> pd.DataFrame:
        """Restituisce la prima tabella che contiene una colonna ``Date``.

        Args:
            tables: Lista di DataFrame estratti da ``pandas.read_html``.

        Returns:
            DataFrame che contiene almeno una colonna denominata ``Date``.

        Raises:
            ValueError: Se nessuna tabella presenta la colonna ``Date``.
        """

        for table in tables:
            normalized_cols = {str(col).strip() for col in table.columns}
            if any(col.lower() == "date" for col in normalized_cols):
                return table
        raise ValueError("No table with 'Date' column found in LBMA payload")

    def _fx_rates_for_dates(self, rome_times: pd.Series) -> pd.Series:
        """Restituisce il cambio USD/EUR per ciascuna osservazione richiesta.

        Args:
            rome_times: Serie di timestamp timezone-aware nel fuso ``Europe/Rome``.

        Returns:
            Serie di cambi USD/EUR allineata all'indice di ``rome_times``.

        Raises:
            ValueError: Se non è possibile reperire i cambi BCE necessari.
        """

        result = pd.Series(index=rome_times.index, dtype=float)
        valid_mask = ~rome_times.isna()
        if not valid_mask.any():
            return result
        normalized = rome_times[valid_mask].dt.normalize()
        dates = [ts.tz_localize(None).date() for ts in normalized]
        missing: set[date_type] = {d for d in dates if d not in self._fx_cache}
        if missing:
            self._load_fx_rates(missing)
        values = [self._fx_cache[d] for d in dates]
        result.loc[valid_mask] = values
        return result

    def _load_fx_rates(self, missing: Iterable[date_type]) -> None:
        """Scarica i cambi USD/EUR per le date mancanti usando il fetcher ECB.

        Args:
            missing: Insieme di date (fuso Europe/Rome) per le quali mancano i
                cambi.

        Raises:
            ValueError: Se dopo il download non risultano disponibili cambi per
                le date richieste.
        """

        if not missing:
            return
        from .ecb import ECBFetcher  # import locale per evitare cicli

        start_date = min(missing)
        fetcher = ECBFetcher(raw_root=self.raw_root, logger=self.logger)
        artifact = fetcher.fetch(symbols=[self.FX_SERIES], start=pd.Timestamp(start_date))
        frame = artifact.data.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
        frame = frame.dropna(subset=["date", "value"]).sort_values("date")
        if frame.empty:
            missing_repr = ", ".join(str(d) for d in sorted(missing))
            msg = f"Missing USD/EUR FX rates for dates: {missing_repr}"
            raise ValueError(msg)
        values = frame.drop_duplicates("date", keep="last").set_index("date")["value"]
        full_index = pd.date_range(values.index.min(), values.index.max(), freq="D")
        filled = values.reindex(full_index, method="ffill")
        for day in missing:
            if day in filled.index:
                self._fx_cache[day] = float(filled.loc[day])
            else:
                previous = filled[filled.index <= day]
                if previous.empty:
                    msg = f"Unable to determine FX rate for {day}"
                    raise ValueError(msg)
                self._fx_cache[day] = float(previous.iloc[-1])

    def _resolve_spec(self, symbol: str) -> MetalSpec:
        """Restituisce la configurazione del metallo richiesto.

        Args:
            symbol: Identificatore della serie LBMA.

        Returns:
            ``MetalSpec`` associato al simbolo richiesto.

        Raises:
            ValueError: Se il simbolo non è supportato.
        """

        try:
            return SERIES[symbol]
        except KeyError as error:  # pragma: no cover - errore informativo
            available = ", ".join(SERIES.keys())
            raise ValueError(f"Unsupported LBMA symbol {symbol}. Available: {available}") from error

    def _normalise_fx_rates(
        self, fx_rates: Mapping[str | datetime | date_type, float] | pd.Series
    ) -> dict[date_type, float]:
        """Converte input eterogenei in un dizionario indicizzato per data.

        Args:
            fx_rates: Mappatura o serie contenente cambi USD/EUR indicizzati per
                data, timestamp o stringa compatibile con ``pd.to_datetime``.

        Returns:
            Dizionario ``{data: cambio}`` con date normalizzate in formato
            ``datetime.date``.
        """

        if isinstance(fx_rates, pd.Series):
            iterable = fx_rates.items()
        else:
            iterable = fx_rates.items()
        normalized: dict[date_type, float] = {}
        for key, value in iterable:
            if isinstance(key, datetime):
                normalized[key.date()] = float(value)
            elif isinstance(key, date_type):
                normalized[key] = float(value)
            else:
                normalized[pd.to_datetime(key).date()] = float(value)
        return normalized

    def _parse_tables(self, html_text: str) -> list[pd.DataFrame]:
        """Estrae tutte le tabelle presenti nell'HTML in DataFrame grezzi.

        Args:
            html_text: Contenuto HTML da cui estrarre le tabelle.

        Returns:
            Lista di DataFrame, uno per ciascuna tabella trovata.
        """

        parser = _HTMLTableParser()
        parser.feed(html_text)
        frames: list[pd.DataFrame] = []
        for header, rows in parser.tables:
            if not rows:
                continue
            width = max(len(header), max((len(row) for row in rows), default=0))
            if width == 0:
                continue
            normalized_rows = [row + [""] * (width - len(row)) for row in rows]
            if header:
                padded_header = header + [""] * (width - len(header))
                columns = [col or f"column_{idx}" for idx, col in enumerate(padded_header)]
            else:
                columns = [f"column_{idx}" for idx in range(width)]
            frame = pd.DataFrame(normalized_rows, columns=columns)
            frames.append(frame)
        return frames


class _HTMLTableParser(HTMLParser):
    """Parser HTML minimale che estrae celle da elementi ``<table>``."""

    def __init__(self) -> None:
        super().__init__()
        self.tables: list[tuple[list[str], list[list[str]]]] = []
        self._in_table = False
        self._current_rows: list[list[str]] = []
        self._header: list[str] = []
        self._current_row: list[str] | None = None
        self._capture_cell = False
        self._cell_data: list[str] = []
        self._row_is_header = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower == "table":
            self._in_table = True
            self._current_rows = []
            self._header = []
        elif self._in_table and tag_lower == "tr":
            self._current_row = []
            self._row_is_header = False
        elif self._in_table and tag_lower in {"td", "th"}:
            self._capture_cell = True
            self._cell_data = []
            if tag_lower == "th":
                self._row_is_header = True

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if not self._in_table:
            return
        if tag_lower in {"td", "th"} and self._capture_cell and self._current_row is not None:
            cell_text = " ".join(part for part in self._cell_data if part).strip()
            self._current_row.append(cell_text)
            self._capture_cell = False
        elif tag_lower == "tr" and self._current_row is not None:
            if self._row_is_header and not self._header:
                self._header = self._current_row
            elif self._current_row:
                self._current_rows.append(self._current_row)
            self._current_row = None
        elif tag_lower == "table":
            if self._current_rows:
                self.tables.append((self._header, self._current_rows))
            self._in_table = False
            self._current_rows = []
            self._header = []
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._capture_cell:
            stripped = data.strip()
            if stripped:
                self._cell_data.append(stripped)
