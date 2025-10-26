"""Funzioni di pulizia serie storiche con spiegazioni italiane."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "HampelConfig",
    "apply_hampel",
    "winsorize_series",
    "clean_price_history",
    "prepare_estimation_copy",
]


@dataclass(slots=True)
class HampelConfig:
    """Parametri per il filtro di Hampel.

    * ``window`` definisce l'ampiezza della finestra centrata utilizzata per
      la mediana e la MAD; deve essere positiva per mantenere coerenza con
      l'intuizione statistica.
    * ``n_sigma`` controlla la soglia di deviazione ammessa prima di etichettare
      un punto come outlier.
    """

    window: int = 7
    n_sigma: float = 3.0

    def __post_init__(self) -> None:
        """Valida i parametri garantendo valori sensati."""

        if self.window <= 0:
            raise ValueError("window deve essere positivo")
        if self.n_sigma <= 0:
            raise ValueError("n_sigma deve essere positivo")


def apply_hampel(series: pd.Series, config: HampelConfig | None = None) -> pd.Series:
    """Applica il filtro di Hampel basato su mediana e MAD per sopprimere spike.

    La procedura individua gli outlier confrontando la distanza assoluta dalla
    mediana con una soglia scalata dalla MAD (`Median Absolute Deviation`).
    Qualsiasi punto che eccede la soglia viene sostituito con la mediana locale
    per evitare impatti sui rendimenti successivi.
    """

    config = config or HampelConfig()
    if series.empty:
        return series
    window = config.window
    # La finestra centrata garantisce simmetria: prendiamo la mediana locale
    # includendo sempre l'osservazione corrente.
    median = series.rolling(window=window, center=True, min_periods=1).median()
    diff = (series - median).abs()
    mad = diff.rolling(window=window, center=True, min_periods=1).median()
    mad = mad.replace(0, np.nan)
    # La costante 1.4826 rende la MAD un estimatore consistente della deviazione
    # standard sotto assunzione di normalità.
    threshold = config.n_sigma * 1.4826 * mad
    threshold = threshold.fillna(0.0)
    mask = diff > threshold
    cleaned = series.copy()
    cleaned[mask] = median[mask]
    return cleaned


def winsorize_series(
    series: pd.Series,
    *,
    lower: float = 0.01,
    upper: float = 0.99,
) -> pd.Series:
    """Taglia la serie entro i quantili indicati per mitigare outlier estremi."""

    if not 0.0 <= lower < upper <= 1.0:
        raise ValueError("intervallo di quantili non valido")
    if series.empty:
        return series
    lower_q, upper_q = series.quantile([lower, upper])
    return series.clip(lower=lower_q, upper=upper_q)


def clean_price_history(
    frame: pd.DataFrame,
    *,
    value_column: str = "price",
    group_column: str = "symbol",
    hampel: HampelConfig | None = None,
) -> pd.DataFrame:
    """Applica il filtro di Hampel per simbolo mantenendo la struttura PIT.

    Lavoriamo su una copia per preservare l'input originale e permettere audit
    comparativi; ogni gruppo viene ripulito indipendentemente per evitare la
    contaminazione tra asset con scale diverse.
    """

    if frame.empty:
        return frame
    if value_column not in frame.columns:
        raise ValueError(f"colonna attesa {value_column}")

    work = frame.copy()
    work[value_column] = work.groupby(group_column, group_keys=False)[value_column].apply(
        lambda s: apply_hampel(s, hampel)
    )
    return work


def prepare_estimation_copy(
    returns: pd.Series,
    *,
    winsor_quantiles: tuple[float, float] = (0.01, 0.99),
) -> pd.Series:
    """Restituisce una copia winsorizzata della serie di rendimenti.

    Questa trasformazione è usata per i percorsi di sola stima, così da
    minimizzare l'effetto di spike residui senza alterare i rendimenti grezzi
    usati per la reportistica.
    """

    lower, upper = winsor_quantiles
    return winsorize_series(returns, lower=lower, upper=upper)
