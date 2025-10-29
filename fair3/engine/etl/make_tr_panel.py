"""Construct the FAIR asset panel from raw ingest artefacts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.etl.calendar import TradingCalendar, build_calendar, reindex_frame
from fair3.engine.etl.cleaning import clean_price_history, prepare_estimation_copy
from fair3.engine.etl.fx import FXFrame, convert_to_base, load_fx_rates
from fair3.engine.etl.qa import QARecord, QAReport, write_qa_log
from fair3.engine.ingest.registry import source_licenses
from fair3.engine.utils.io import ensure_dir
from fair3.engine.utils.storage import ASSET_PANEL_SCHEMA, persist_parquet

__all__ = ["TRPanelArtifacts", "TRPanelBuilder", "PanelBuilder", "build_tr_panel"]


@dataclass(slots=True)
class TRPanelArtifacts:
    """Percorsi e metadati del pannello asset normalizzato dall'ETL."""

    panel_path: Path
    checksum: str
    qa_path: Path
    symbols: list[str]
    rows: int


class TRPanelBuilder:
    """Orchestratore dell'ETL che produce il pannello prezzi/rendimenti.

    La classe incapsula path di lavoro e valuta base per favorire test
    end-to-end; ogni step intermedio è reso metodico così da poter essere
    verificato e riutilizzato in contesti batch o notebook.
    """

    def __init__(
        self,
        *,
        raw_root: Path | str = Path("data") / "raw",
        clean_root: Path | str = Path("data") / "clean",
        audit_root: Path | str = Path("audit"),
        base_currency: str = "EUR",
    ) -> None:
        self.raw_root = Path(raw_root)
        self.clean_root = Path(clean_root)
        self.audit_root = Path(audit_root)
        self.base_currency = base_currency
        self._license_map = source_licenses()

    # ------------------------------------------------------------------
    def build(self, *, seed: int | None = None, trace: bool = False) -> TRPanelArtifacts:
        """Esegue l'intera pipeline e ritorna i percorsi degli output."""

        run_ts = datetime.now(UTC)
        raw_records = self._load_raw_records()
        if not raw_records:
            raise FileNotFoundError(
                "Nessun file raw trovato. Eseguire prima `fair3 ingest` per popolare i dati."
            )

        if trace:
            print(f"[fair3.etl] file_raw={len(raw_records)}")
        calendar = self._build_calendar(raw_records)
        fx_frame = self._build_fx_frame(raw_records)

        prices, qa_report = self._prepare_prices(raw_records, calendar, fx_frame)
        returns = self._compute_returns(prices, trace=trace)
        features = self._compute_features(returns, seed=seed)
        panel = self._assemble_panel(prices, returns, features, run_ts)
        panel_path, checksum = persist_parquet(
            panel,
            self.clean_root / "asset_panel.parquet",
            ASSET_PANEL_SCHEMA,
        )
        qa_path = write_qa_log(qa_report, self.audit_root / "qa_data_log.csv")

        return TRPanelArtifacts(
            panel_path=panel_path,
            checksum=checksum,
            qa_path=qa_path,
            symbols=sorted({idx[1] for idx in prices.index}),
            rows=len(panel),
        )

    # ------------------------------------------------------------------
    def _load_raw_records(self) -> list[pd.DataFrame]:
        """Carica i CSV raw e li normalizza in un formato uniforme."""

        records: list[pd.DataFrame] = []
        for path in sorted(self.raw_root.glob("*/*.csv")):
            frame = pd.read_csv(path)
            if frame.empty:
                continue
            if {"date", "value", "symbol"} - set(frame.columns):
                msg = f"il file raw {path} non contiene le colonne date/value/symbol"
                raise ValueError(msg)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
            frame = frame.dropna(subset=["date"]).reset_index(drop=True)
            frame["source"] = path.parent.name
            if "currency" not in frame.columns:
                frame["currency"] = self.base_currency
            frame = frame.rename(columns={"value": "price"})
            # Annotiamo la sorgente per alimentare i log QA e permettere audit.
            records.append(frame)
        return records

    def _build_calendar(self, records: list[pd.DataFrame]) -> TradingCalendar:
        """Aggrega tutte le date disponibili per definire il calendario PIT."""

        by_symbol: dict[str, pd.DataFrame] = {}
        for frame in records:
            for symbol, sub in frame.groupby("symbol"):
                existing = by_symbol.get(symbol)
                keep = sub[["date", "price"]].copy()
                if existing is None:
                    by_symbol[symbol] = keep
                else:
                    by_symbol[symbol] = pd.concat([existing, keep], ignore_index=True)
        return build_calendar(by_symbol, name="raw_union")

    def _build_fx_frame(self, records: list[pd.DataFrame]) -> FXFrame:
        """Estrarre eventuali serie FX dai record raw e costruire `FXFrame`."""

        fx_candidates: list[pd.DataFrame] = []
        for frame in records:
            if frame["symbol"].str.contains("/").any():
                fx_candidates.append(frame.rename(columns={"price": "value"}))
        if not fx_candidates:
            return FXFrame(base_currency=self.base_currency, rates=pd.DataFrame())
        return load_fx_rates(fx_candidates, self.base_currency)

    def _prepare_prices(
        self,
        records: list[pd.DataFrame],
        calendar: TradingCalendar,
        fx_frame: FXFrame,
    ) -> tuple[pd.DataFrame, QAReport]:
        """Pulizia, riallineamento e conversione FX dei prezzi raw."""

        combined: list[pd.DataFrame] = []
        qa_report = QAReport(records=[])
        for frame in records:
            source = frame["source"].iat[0]
            license_label = self._license_map.get(source, "see_source")
            for symbol, sub in frame.groupby("symbol"):
                if "/" in symbol:
                    # I file FX vengono gestiti separatamente e non partecipano
                    # al pannello prezzi diretto.
                    continue
                working = sub[["date", "price", "currency"]].copy()
                working["symbol"] = symbol
                working = reindex_frame(
                    working,
                    calendar=calendar,
                    group_cols=["symbol"],
                    value_cols=["price", "currency"],
                )
                original_price = working["price"].copy()
                working = clean_price_history(working, value_column="price", group_column="symbol")
                outliers = int((original_price != working["price"]).sum())
                working = convert_to_base(
                    working.assign(symbol=symbol, source=source),
                    fx=fx_frame,
                    value_column="price",
                    currency_column="currency",
                )
                working = working.assign(source=source, license=license_label)
                start = working["date"].min().to_pydatetime() if not working.empty else None
                end = working["date"].max().to_pydatetime() if not working.empty else None
                qa_record = QARecord(
                    symbol=symbol,
                    source=source,
                    currency=self.base_currency,
                    start=start,
                    end=end,
                    rows=int(len(working)),
                    nulls=int(working["price"].isna().sum()),
                    outliers=outliers,
                )
                qa_report.append(qa_record)
                combined.append(working)
        if not combined:
            raise RuntimeError("Nessun dato prezzo disponibile dopo la pulizia")
        prices = pd.concat(combined, ignore_index=True)
        prices = prices.sort_values(["date", "symbol"]).set_index(["date", "symbol"])
        return prices, qa_report

    def _compute_returns(self, prices: pd.DataFrame, *, trace: bool = False) -> pd.DataFrame:
        # Calcoliamo rendimenti semplici/log per simbolo e sanifichiamo inf/nan.
        returns = (
            prices[["price"]]
            .groupby(level="symbol")
            .pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
        )
        returns = returns.fillna(0.0)
        log_returns = np.log1p(returns)
        log_returns = log_returns.replace([np.inf, -np.inf], 0.0)
        simple_ret = returns["price"]
        log_ret = log_returns["price"]

        dup_mask = simple_ret.index.duplicated(keep="last")
        dropped_simple = int(dup_mask.sum())
        if dropped_simple:
            if trace:
                print(f"[fair3.etl] righe_duplicate_rendimenti={dropped_simple}")
            simple_ret = simple_ret[~dup_mask]
            log_ret = log_ret[~dup_mask]

        # La copia per stima viene winsorizzata per proteggere i modelli da code.
        estimation = log_ret.groupby(level="symbol").apply(prepare_estimation_copy)
        if isinstance(estimation.index, pd.MultiIndex) and estimation.index.nlevels > 2:
            estimation.index = estimation.index.droplevel(0)
        dup_estimation = estimation.index.duplicated(keep="last")
        dropped_estimation = int(dup_estimation.sum())
        if dropped_estimation:
            if trace:
                print(f"[fair3.etl] righe_duplicate_stima={dropped_estimation}")
            estimation = estimation[~dup_estimation]
        estimation = estimation.reindex(simple_ret.index)

        out = pd.DataFrame(
            {
                "ret": simple_ret,
                "log_ret": log_ret,
                "log_ret_estimation": estimation,
            }
        )
        return out

    def _compute_features(self, returns: pd.DataFrame, *, seed: int | None) -> pd.DataFrame:
        rng = np.random.default_rng(seed if seed is not None else 0)
        group = returns.groupby(level="symbol")

        def _lagged_mean(series: pd.Series, window: int, min_periods: int) -> pd.Series:
            """Media mobile ritardata di una finestra specifica."""

            return series.shift(1).rolling(window, min_periods=min_periods).mean()

        def _lagged_std(series: pd.Series, window: int, min_periods: int) -> pd.Series:
            """Deviazione standard mobile ritardata, robusta ai buchi iniziali."""

            return series.shift(1).rolling(window, min_periods=min_periods).std()

        ma_5 = group["log_ret"].transform(lambda s: _lagged_mean(s, 5, 1))
        ma_21 = group["log_ret"].transform(lambda s: _lagged_mean(s, 21, 1))
        vol_21 = group["log_ret"].transform(lambda s: _lagged_std(s, 21, 5))
        vol_floor = rng.uniform(1e-8, 1e-6)
        # Il floor evita volatilità nulla che rompenderebbe successive divisioni.
        vol_21 = vol_21.fillna(vol_floor)
        features = pd.DataFrame(
            {
                "lag_ma_5": ma_5,
                "lag_ma_21": ma_21,
                "lag_vol_21": vol_21,
            }
        )
        return features

    def _assemble_panel(
        self,
        prices: pd.DataFrame,
        returns: pd.DataFrame,
        features: pd.DataFrame,
        run_ts: datetime,
    ) -> pd.DataFrame:
        """Converte prezzi, rendimenti e feature nel pannello lungo richiesto."""

        ensure_dir(self.clean_root)
        base = prices.reset_index()
        base["date"] = pd.to_datetime(base["date"])  # type: ignore[arg-type]
        base["date"] = base["date"].dt.tz_localize("Europe/Rome").dt.tz_convert("UTC")
        base["currency"] = self.base_currency
        base["tz"] = "Europe/Rome"
        base["quality_flag"] = "clean"
        base["license"] = base["license"].fillna("see_source")
        revision_tag = f"etl_{run_ts.strftime('%Y%m%dT%H%M%SZ')}"
        base["revision_tag"] = revision_tag

        returns_frame = returns.reset_index()
        returns_frame["date"] = pd.to_datetime(returns_frame["date"])
        returns_frame["date"] = (
            returns_frame["date"].dt.tz_localize("Europe/Rome").dt.tz_convert("UTC")
        )

        features_frame = features.reset_index()
        features_frame["date"] = pd.to_datetime(features_frame["date"])
        features_frame["date"] = (
            features_frame["date"].dt.tz_localize("Europe/Rome").dt.tz_convert("UTC")
        )

        combined = base.merge(returns_frame, on=["date", "symbol"], how="left")
        combined = combined.merge(features_frame, on=["date", "symbol"], how="left")

        def _build_field(field_name: str, column: str) -> pd.DataFrame:
            values = pd.to_numeric(combined[column], errors="coerce")
            frame = combined[
                [
                    "date",
                    "symbol",
                    "currency",
                    "source",
                    "license",
                    "tz",
                    "quality_flag",
                    "revision_tag",
                ]
            ].copy()
            frame["field"] = field_name
            frame["value"] = values.astype(float)
            frame["pit_flag"] = np.int8(1)
            return frame

        field_map = {
            "adj_close": "price",
            "ret": "ret",
            "log_ret": "log_ret",
            "log_ret_estimation": "log_ret_estimation",
            "lag_ma_5": "lag_ma_5",
            "lag_ma_21": "lag_ma_21",
            "lag_vol_21": "lag_vol_21",
        }
        frames: list[pd.DataFrame] = []
        for field_name, column in field_map.items():
            if column not in combined.columns:
                continue
            field_frame = _build_field(field_name, column)
            frames.append(field_frame.dropna(subset=["value"]))
        panel = pd.concat(frames, ignore_index=True)
        panel = panel.sort_values(["date", "symbol", "field"]).reset_index(drop=True)

        def _checksum(row: pd.Series) -> str:
            payload = "|".join(
                [
                    row["symbol"],
                    row["field"],
                    row["date"].isoformat(),
                    f"{row['value']:.12f}",
                ]
            )
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()

        panel["checksum"] = panel.apply(_checksum, axis=1)
        panel["currency"] = panel["currency"].fillna(self.base_currency)
        return panel


def build_tr_panel(**kwargs: object) -> TRPanelArtifacts:
    builder = TRPanelBuilder(**kwargs)
    return builder.build()


PanelBuilder = TRPanelBuilder
