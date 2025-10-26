"""Test esaustivi per la gestione dei seed nel modulo ``rand``."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pytest
import yaml

from fair3.engine.utils import rand


def test_load_seeds_torna_default_se_file_mancante(tmp_path: Path) -> None:
    """Se il file non esiste deve essere restituito lo stream ``global`` di default."""

    percorso = tmp_path / "assenza.yml"
    assert percorso.exists() is False

    risultato = rand.load_seeds(percorso)

    assert risultato == {rand.DEFAULT_STREAM: rand.DEFAULT_SEED}


def test_load_seeds_legge_formato_annidato(tmp_path: Path) -> None:
    """Il loader deve gestire file con sezione ``seeds`` annidata."""

    contenuto = {"seeds": {"global": 7, "factors": 99}}
    percorso = tmp_path / "seeds.yml"
    percorso.write_text(json.dumps(contenuto), encoding="utf-8")

    risultato = rand.load_seeds(percorso)

    assert risultato["global"] == 7
    assert risultato["factors"] == 99


def test_load_seeds_rileva_formati_non_mappabili(tmp_path: Path) -> None:
    """Formati YAML non mappabili devono provocare un ``TypeError``."""

    percorso = tmp_path / "seeds.yml"
    percorso.write_text("- 1\n- 2\n", encoding="utf-8")

    with pytest.raises(TypeError):
        rand.load_seeds(percorso)


def test_save_seeds_scrive_yaml_normalizzato(tmp_path: Path) -> None:
    """Il salvataggio deve produrre chiavi ordinate e tipizzate come interi."""

    percorso = tmp_path / "custom.yml"
    esito = rand.save_seeds({"factors": 11, "global": 2}, seed_path=percorso)

    assert esito == percorso
    contenuto = yaml.safe_load(percorso.read_text(encoding="utf-8"))
    assert contenuto == {"seeds": {"factors": 11, "global": 2}}


def test_seed_for_stream_usa_mappatura_in_memoria() -> None:
    """Quando la mappa è fornita non deve essere letto alcun file."""

    seeds = {"global": 1, "altro": 9}
    assert rand.seed_for_stream("altro", seeds=seeds) == 9


def test_generator_from_seed_riusa_generatore_esistente() -> None:
    """Se viene passato un ``Generator`` deve essere restituito invariato."""

    generatore = np.random.default_rng(123)
    assert rand.generator_from_seed(generatore) is generatore


def test_generator_from_seed_rende_output_deterministico(tmp_path: Path) -> None:
    """Stream identici devono produrre sequenze identiche di numeri casuali."""

    percorso = tmp_path / "seeds.yml"
    percorso.write_text("seeds:\n  global: 123\n  fattori: 987\n", encoding="utf-8")

    rng_a = rand.generator_from_seed(stream="fattori", seed_path=percorso)
    rng_b = rand.generator_from_seed(stream="fattori", seed_path=percorso)

    assert np.allclose(rng_a.normal(size=4), rng_b.normal(size=4))


def test_broadcast_seed_sincronizza_python_e_numpy() -> None:
    """La funzione deve allineare sia ``random`` che ``numpy.random``."""

    rand.broadcast_seed(2024)
    valore_python_1 = random.random()
    valore_numpy_1 = float(np.random.rand())

    rand.broadcast_seed(2024)
    valore_python_2 = random.random()
    valore_numpy_2 = float(np.random.rand())

    assert valore_python_1 == pytest.approx(valore_python_2)
    assert valore_numpy_1 == pytest.approx(valore_numpy_2)


def test_spawn_child_rng_rispetta_jumps_e_sollevamenti() -> None:
    """I figli devono essere riproducibili e validare ``jumps``."""

    parent = np.random.default_rng(0)
    child_a = rand.spawn_child_rng(parent, jumps=3)
    child_b = rand.spawn_child_rng(parent, jumps=3)

    assert np.allclose(child_a.random(5), child_b.random(5))

    with pytest.raises(ValueError):
        rand.spawn_child_rng(parent, jumps=0)
