"""Test per l'inventario delle funzioni Python.

Queste verifiche garantiscono che lo strumento di audit rilevi correttamente le
funzioni presenti nel progetto e produca un JSON utilizzabile dal team QA.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from audit import function_inventory


@pytest.fixture
def inventario_tmp(tmp_path: Path) -> Path:
    """Restituisce il percorso di un file temporaneo per l'inventario."""

    return tmp_path / "inventario.json"


def test_build_inventory_raccoglie_funzioni_note() -> None:
    """L'inventario deve includere una funzione nota del modulo CLI."""

    inventory = function_inventory.build_inventory()
    nomi = {record.qualifica for record in inventory if record.percorso == "fair3/cli/main.py"}
    assert "main" in nomi, "La funzione main del CLI deve comparire nell'inventario"


def test_save_inventory_crea_json_ben_formato(inventario_tmp: Path) -> None:
    """Il salvataggio deve produrre JSON UTF-8 con chiavi attese."""

    function_inventory.save_inventory(inventario_tmp)
    contenuto = json.loads(inventario_tmp.read_text(encoding="utf-8"))
    assert contenuto, "L'inventario non può essere vuoto"
    campione = contenuto[0]
    expected_keys = {
        "percorso",
        "qualifica",
        "tipo",
        "linea",
        "argomenti",
        "ha_docstring",
    }
    assert expected_keys <= campione.keys()
