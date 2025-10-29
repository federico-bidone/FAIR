"""Fetcher e funzioni di compositing per i preset sintetici di testfol.io.

Il sito testfol.io pubblica serie storiche sintetiche (es. ``SPYSIM``, ``VTISIM``,
``GLDSIM``) costruite concatenando fonti eterogenee (Shiller, Schwert,
Portfolio Visualizer, dati ETF moderni) con eventuali aggiustamenti
percentuali. Poiché la licenza impone il download manuale dei file sorgente e
non è disponibile un endpoint pubblico, questo modulo fornisce un fetcher che
legge una configurazione YAML dichiarativa e combina i segmenti salvati in
locale sotto ``data/testfolio_manual/``.

Il formato YAML prevede una sezione ``presets`` con un dizionario che descrive
ogni serie sintetica. Ogni preset elenca uno o più ``segments``: ciascun
segmento può puntare a un file CSV manuale, specificare le colonne data/valore,
lo scaling percentuale→decimale e un eventuale aggiustamento annualizzato da
applicare a ogni periodo (per esempio il +0.0945% annuo documentato da
Portfolio Visualizer per compensare costi operativi).

Esempio minimale di configurazione (inserito in ``configs/testfolio_presets.yml``):

```
presets:
  spysim:
    frequency: monthly
    description: "Synthetic US equity index used by testfol.io"
    segments:
      - loader: manual_csv
        path: spysim_pre_etf.csv
        date_column: Date
        value_column: Return
        scale: 0.01
        month_end_align: true
      - loader: manual_csv
        path: spysim_post_1993.csv
        date_column: date
        value_column: total_return
        annualized_adjustment: 0.000945
```

L'utente deve popolare ``data/testfolio_manual/`` con i file CSV indicati nel
config e invocare ``fair3 ingest --source testfolio`` per generare un artefatto
CSV normalizzato (colonne ``date``, ``value``, ``symbol``) sotto
``data/raw/testfolio``. In caso di file mancanti il fetcher solleva un
``FileNotFoundError`` con istruzioni esplicite.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from pandas.tseries.offsets import MonthEnd

from .registry import BaseCSVFetcher, IngestArtifact


@dataclass(frozen=True)
class PresetSegmentSpec:
    """Descrive un segmento componente di una serie sintetica testfol.io.

    Attributes:
        loader: Strategia di caricamento (attualmente solo ``manual_csv``).
        path: Percorso relativo del file CSV rispetto a ``manual_root``.
        date_column: Nome della colonna contenente la data.
        value_column: Nome della colonna con il valore/ritorno.
        scale: Fattore moltiplicativo (es. 0.01 per convertire percentuali).
        frequency: Frequenza del segmento (``monthly``/``daily``/``annual``).
        month_end_align: Se ``True`` forza le date a fine mese (utile per dati
            mensili espressi con timestamp di inizio periodo).
        start: Data minima opzionale da mantenere per il segmento.
        end: Data massima opzionale per troncare il segmento.
        annualized_adjustment: Rendimento annualizzato da aggiungere a ogni
            osservazione del segmento (valore decimale, es. 0.000945 → 0.0945%).
        notes: Eventuali note esplicative (propagate nei metadati).
    """

    loader: str
    path: str
    date_column: str = "date"
    value_column: str = "value"
    scale: float = 1.0
    frequency: str = "monthly"
    month_end_align: bool = False
    start: pd.Timestamp | None = None
    end: pd.Timestamp | None = None
    annualized_adjustment: float = 0.0
    notes: str | None = None

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        default_frequency: str,
    ) -> PresetSegmentSpec:
        """Costruisce ``PresetSegmentSpec`` validando chiavi obbligatorie.

        Args:
            data: Mappatura proveniente dal file YAML.
            default_frequency: Frequenza ereditata dalla definizione del preset.

        Returns:
            Istanza pronta per il caricamento del segmento.

        Raises:
            ValueError: Se mancano campi obbligatori o il loader non è supportato.
        """

        loader = data.get("loader", "manual_csv")
        if loader != "manual_csv":
            msg = f"Unsupported loader '{loader}' in testfolio preset configuration"
            raise ValueError(msg)
        path = data.get("path")
        if not path:
            raise ValueError("Each testfolio segment must declare a 'path'")
        start = pd.to_datetime(data.get("start")) if data.get("start") else None
        end = pd.to_datetime(data.get("end")) if data.get("end") else None
        frequency = data.get("frequency", default_frequency)
        return cls(
            loader=loader,
            path=str(path),
            date_column=str(data.get("date_column", "date")),
            value_column=str(data.get("value_column", "value")),
            scale=float(data.get("scale", 1.0)),
            frequency=str(frequency),
            month_end_align=bool(data.get("month_end_align", False)),
            start=start,
            end=end,
            annualized_adjustment=float(data.get("annualized_adjustment", 0.0)),
            notes=data.get("notes"),
        )


def _annual_to_periodic(rate: float, frequency: str) -> float:
    """Converte un tasso annualizzato in incremento per periodo discreto.

    Args:
        rate: Rendimento annualizzato espresso in forma decimale.
        frequency: Frequenza del segmento (``monthly``, ``daily``, ``weekly``,
            ``annual``).

    Returns:
        Rendimento da sommare a ciascuna osservazione del segmento.

    Raises:
        ValueError: Se la frequenza non è riconosciuta.
    """

    if rate == 0.0:
        return 0.0
    frequency_norm = frequency.lower()
    if frequency_norm == "monthly":
        periods = 12
    elif frequency_norm == "weekly":
        periods = 52
    elif frequency_norm == "daily":
        periods = 252
    elif frequency_norm == "annual":
        periods = 1
    else:
        raise ValueError(f"Unsupported frequency '{frequency}' for annual conversion")
    return (1.0 + rate) ** (1.0 / periods) - 1.0


def curate_testfolio_presets(
    config_path: Path | str,
    *,
    manual_root: Path | str,
) -> dict[str, pd.DataFrame]:
    """Legge la configurazione YAML e compone i preset testfol.io locali.

    Args:
        config_path: Percorso al file YAML con la sezione ``presets``.
        manual_root: Directory contenente i file CSV dei segmenti manuali.

    Returns:
        Dizionario ``{preset: DataFrame}`` con colonne ``date`` (``datetime64[ns]``)
        e ``value`` (``float``) già normalizzate in forma decimale.

    Raises:
        FileNotFoundError: Se il file YAML o un CSV segmentato non sono presenti.
        ValueError: Se la configurazione è malformata o mancano sezioni richieste.
    """

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(
            f"Testfolio configuration file not found: {config_file}"  # pragma: no cover
        )
    with config_file.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, Mapping) or "presets" not in payload:
        raise ValueError("Invalid testfolio configuration: missing 'presets' mapping")
    presets_section = payload["presets"]
    if not isinstance(presets_section, Mapping):
        raise ValueError("Invalid testfolio configuration: 'presets' must be a mapping")

    manual_dir = Path(manual_root)
    result: dict[str, pd.DataFrame] = {}
    for preset_key, preset_cfg in presets_section.items():
        if not isinstance(preset_cfg, Mapping):
            raise ValueError(f"Preset '{preset_key}' configuration must be a mapping")
        segments_cfg = preset_cfg.get("segments")
        if not isinstance(segments_cfg, Iterable):
            raise ValueError(f"Preset '{preset_key}' must define a 'segments' list")
        frequency = str(preset_cfg.get("frequency", "monthly"))
        output_symbol = str(preset_cfg.get("symbol", preset_key))
        frames: list[pd.DataFrame] = []
        for segment_data in segments_cfg:
            if not isinstance(segment_data, Mapping):
                raise ValueError(f"Preset '{preset_key}' segment must be a mapping")
            segment_spec = PresetSegmentSpec.from_mapping(
                segment_data,
                default_frequency=frequency,
            )
            frame = _load_manual_segment(
                manual_dir=manual_dir,
                segment=segment_spec,
                preset_name=output_symbol,
            )
            frames.append(frame)
        if not frames:
            raise ValueError(f"Preset '{preset_key}' did not yield any segment frames")
        combined = pd.concat(frames, ignore_index=True)
        combined = combined.sort_values("date")
        combined = combined.drop_duplicates(subset=["date"], keep="last")
        combined = combined.reset_index(drop=True)
        result[output_symbol] = combined
    return result


def _load_manual_segment(
    *,
    manual_dir: Path,
    segment: PresetSegmentSpec,
    preset_name: str,
) -> pd.DataFrame:
    """Carica un segmento manuale normalizzandolo nello schema FAIR.

    Args:
        manual_dir: Directory base che contiene i file CSV manuali.
        segment: Specifica dichiarativa del segmento da caricare.
        preset_name: Nome simbolo finale da assegnare alle righe prodotte.

    Returns:
        DataFrame con colonne ``date``, ``value`` e ``symbol`` già filtrate in
        base alle opzioni del segmento.

    Raises:
        FileNotFoundError: Se il file CSV dichiarato non è presente.
        ValueError: Se mancano le colonne attese oppure se la frequenza non è
            supportata durante la conversione del tasso annualizzato.
    """

    csv_path = manual_dir / segment.path
    if not csv_path.exists():
        msg = (
            "Missing manual CSV for testfol.io preset. Download the referenced "
            f"file and place it under {csv_path}."
        )
        raise FileNotFoundError(msg)
    frame = pd.read_csv(csv_path)
    if segment.date_column not in frame.columns:
        raise ValueError(f"Column '{segment.date_column}' not found in manual CSV {csv_path}")
    if segment.value_column not in frame.columns:
        raise ValueError(f"Column '{segment.value_column}' not found in manual CSV {csv_path}")
    dates = pd.to_datetime(frame[segment.date_column], errors="coerce")
    if segment.month_end_align:
        dates = dates + MonthEnd(0)
    values = pd.to_numeric(frame[segment.value_column], errors="coerce") * segment.scale
    data = pd.DataFrame({"date": dates, "value": values})
    data = data.dropna(subset=["date", "value"])
    if segment.start is not None:
        data = data[data["date"] >= segment.start]
    if segment.end is not None:
        data = data[data["date"] <= segment.end]
    if segment.annualized_adjustment:
        increment = _annual_to_periodic(
            segment.annualized_adjustment,
            segment.frequency,
        )
        data["value"] = data["value"] + increment
    data = data.reset_index(drop=True)
    data["symbol"] = preset_name
    return data


class TestfolioPresetFetcher(BaseCSVFetcher):
    """Fetcher manuale basato su configurazione YAML per i preset testfol.io."""

    SOURCE = "testfolio"
    LICENSE = "testfol.io synthetic presets — informational/educational use"
    BASE_URL = "https://testfol.io"
    DEFAULT_SYMBOLS: tuple[str, ...] = ()
    __test__ = False

    def __init__(
        self,
        *,
        config_path: Path | str | None = None,
        manual_root: Path | str | None = None,
        raw_root: Path | str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(raw_root=raw_root, **kwargs)
        self.config_path = (
            Path(config_path)
            if config_path is not None
            else Path("configs") / "testfolio_presets.yml"
        )
        self.manual_root = (
            Path(manual_root) if manual_root is not None else Path("data") / "testfolio_manual"
        )

    def fetch(
        self,
        *,
        symbols: Iterable[str] | None = None,
        start: date | datetime | None = None,
        as_of: datetime | None = None,
        progress: bool = False,
        session: object | None = None,
    ) -> IngestArtifact:
        """Compone i preset testfol.io richiesti applicando eventuali filtri.

        Args:
            symbols: Elenco di preset da comporre; se ``None`` usa tutti quelli
                definiti nella configurazione YAML.
            start: Data minima da mantenere nelle serie risultanti.
            as_of: Timestamp usato per etichettare il file CSV prodotto.
            progress: Flag compatibile con l'interfaccia base; non abilita barre
                di avanzamento per i preset manuali.
            session: Parametro compatibile con ``BaseCSVFetcher`` e ignorato
                poiché non vengono eseguite richieste HTTP.

        Returns:
            Artefatto di ingest con dati concatenati e metadati di audit.

        Raises:
            ValueError: Se viene richiesto un preset non definito oppure se la
                lista dei simboli è vuota.
        """

        del session, progress  # pragma: no cover - compatibilità firma
        presets = curate_testfolio_presets(
            self.config_path,
            manual_root=self.manual_root,
        )
        if symbols is None:
            requested = list(presets.keys())
        else:
            requested = [str(symbol) for symbol in symbols]
        if not requested:
            raise ValueError("At least one symbol must be provided")

        timestamp = as_of or datetime.now(UTC)
        start_ts = pd.to_datetime(start) if start is not None else None
        frames: list[pd.DataFrame] = []
        requests_meta: list[MutableMapping[str, Any]] = []

        for symbol in requested:
            if symbol not in presets:
                raise ValueError(f"Unknown testfolio preset '{symbol}'")
            frame = presets[symbol]
            if start_ts is not None:
                frame = frame[frame["date"] >= start_ts]
            frame = frame.sort_values("date").reset_index(drop=True)
            frames.append(frame)
            requests_meta.append(
                {
                    "symbol": symbol,
                    "config": str(self.config_path),
                    "rows": len(frame),
                }
            )
            self.logger.info(
                "ingest_complete source=%s symbol=%s rows=%d license=%s config=%s",
                self.SOURCE,
                symbol,
                len(frame),
                self.LICENSE,
                self.config_path,
            )

        if frames:
            data = pd.concat(frames, ignore_index=True)
        else:
            data = pd.DataFrame(columns=["date", "value", "symbol"])

        path = self._write_csv(data, timestamp)
        metadata: MutableMapping[str, Any] = {
            "license": self.LICENSE,
            "as_of": timestamp.isoformat(),
            "requests": requests_meta,
            "start": start_ts.isoformat() if start_ts is not None else None,
        }
        return IngestArtifact(
            source=self.SOURCE,
            path=path,
            data=data,
            metadata=metadata,
        )

    def build_url(self, symbol: str, start: pd.Timestamp | None) -> str:  # pragma: no cover
        """Metodo ereditato: non utilizzato, presente per compatibilità."""

        del symbol, start
        return "config://testfolio"

    def parse(self, payload: str, symbol: str) -> pd.DataFrame:  # pragma: no cover
        """Metodo ereditato: non utilizzato, presente per compatibilità."""

        del payload, symbol
        raise NotImplementedError(
            "TestfolioPresetFetcher does not implement direct payload parsing"
        )
