"""Suite di test italiani per ``fair3.engine.etl.cleaning``."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from fair3.engine.etl import cleaning


def test_hampel_config_valida_parametri() -> None:
    """Valori non positivi devono generare messaggi esplicativi."""

    with pytest.raises(ValueError, match="window deve essere positivo"):
        cleaning.HampelConfig(window=0)
    with pytest.raises(ValueError, match="n_sigma deve essere positivo"):
        cleaning.HampelConfig(n_sigma=0)


def test_apply_hampel_sostituisce_spike() -> None:
    """Un picco isolato deve essere riportato alla mediana locale."""

    serie = pd.Series([1.0, 100.0, 1.1, 1.2, 1.1])
    filtrata = cleaning.apply_hampel(serie, cleaning.HampelConfig(window=3, n_sigma=0.5))
    assert pytest.approx(filtrata.iloc[1]) == pytest.approx(1.1)


def test_winsorize_series_valida_intervallo() -> None:
    """Gli intervalli disordinati vengono rigettati con ValueError."""

    with pytest.raises(ValueError, match="intervallo di quantili non valido"):
        cleaning.winsorize_series(pd.Series([1, 2, 3]), lower=0.9, upper=0.2)


def test_clean_price_history_per_symbol() -> None:
    """Ogni simbolo deve essere ripulito indipendentemente."""

    dati = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA", "BBB", "BBB", "BBB"],
            "price": [1.0, 50.0, 1.1, 2.0, 2.0, 2.0],
            "currency": ["EUR"] * 6,
        }
    )
    pulito = cleaning.clean_price_history(
        dati,
        value_column="price",
        group_column="symbol",
        hampel=cleaning.HampelConfig(window=3, n_sigma=0.5),
    )
    assert pulito.loc[1, "price"] != 50.0
    bbb = pulito[pulito["symbol"] == "BBB"]["price"].tolist()
    assert bbb == pytest.approx([2.0, 2.0, 2.0])


def test_prepare_estimation_copy_winsorizza_code() -> None:
    """La serie per la stima deve essere limitata ai quantili dati."""

    rng = np.random.default_rng(0)
    serie = pd.Series(rng.normal(size=1_000))
    serie.iloc[0] = 10.0
    stima = cleaning.prepare_estimation_copy(serie, winsor_quantiles=(0.01, 0.99))
    assert stima.iloc[0] < 10.0
