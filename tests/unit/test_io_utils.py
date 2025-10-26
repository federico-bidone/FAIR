"""Test approfonditi per ``fair3.engine.utils.io`` con scenari italiani."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fair3.engine.utils import io


def test_ensure_dir_crea_cartella_e_restituisce_path(tmp_path: Path) -> None:
    """La funzione deve creare la directory richiesta e ritornare ``Path``."""

    destinazione = tmp_path / "nuova" / "cartella"
    risultato = io.ensure_dir(destinazione)
    assert risultato == destinazione
    assert destinazione.exists() and destinazione.is_dir()


@pytest.mark.parametrize(
    "nome, atteso",
    [
        ("dataset:annuale", "dataset-annuale"),
        ("nome con spazio ", "nome con spazio"),
        ("**stella**", "--stella--"),
    ],
)
def test_safe_path_segment_ripulisce_caratteri_illegali(nome: str, atteso: str) -> None:
    """Il segmento sanificato non deve contenere caratteri proibiti."""

    assert io.safe_path_segment(nome) == atteso


def test_artifact_path_puo_evitare_creazione(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Il parametro ``create`` consente di lasciare non creata la cartella padre."""

    monkeypatch.setattr(io, "ARTIFACTS_ROOT", tmp_path)
    percorso = io.artifact_path("sotto", "file.txt", create=False)
    assert percorso == tmp_path / "sotto" / "file.txt"
    assert not (tmp_path / "sotto").exists()


def test_read_write_yaml_roundtrip(tmp_path: Path) -> None:
    """Scrittura e lettura YAML devono preservare la struttura dati."""

    struttura = {"chiave": [1, 2, {"interno": True}]}
    destinazione = tmp_path / "config.yml"
    scritto = io.write_yaml(struttura, destinazione)
    assert scritto == destinazione
    letto = io.read_yaml(destinazione)
    assert letto == struttura


def test_sha256_file_supporta_chunk_personalizzato(tmp_path: Path) -> None:
    """L'hash deve essere identico indipendentemente dalla dimensione chunk."""

    target = tmp_path / "dati.bin"
    target.write_bytes(b"abc" * 10_000)
    digest_default = io.sha256_file(target)
    digest_piccolo = io.sha256_file(target, chunk_size=17)
    assert digest_default == digest_piccolo


def test_compute_checksums_ignora_file_mancanti(tmp_path: Path) -> None:
    """I percorsi inesistenti vengono ignorati per non interrompere il batch."""

    esistente = tmp_path / "presente.txt"
    esistente.write_text("contenuto", encoding="utf-8")
    risultato = io.compute_checksums([esistente, tmp_path / "assente.txt"])
    assert list(risultato) == [str(esistente)]


def test_copy_with_timestamp_copia_file_con_nome_prevedibile(tmp_path: Path) -> None:
    """La copia deve includere il timestamp e supportare un prefisso custom."""

    sorgente = tmp_path / "origine.csv"
    sorgente.write_text("dati", encoding="utf-8")
    destinazione = tmp_path / "destinazione"
    istante = datetime(2023, 6, 1, 12, 34, 56, tzinfo=UTC)
    risultato = io.copy_with_timestamp(sorgente, destinazione, prefix="snapshot", timestamp=istante)
    atteso = destinazione / "snapshot_20230601T123456Z.csv"
    assert risultato == atteso
    assert risultato.read_text(encoding="utf-8") == "dati"


def test_copy_with_timestamp_percorso_mancante_sollevato(tmp_path: Path) -> None:
    """Quando il file sorgente non esiste deve essere sollevato ``FileNotFoundError``."""

    destinazione = tmp_path / "dest"
    with pytest.raises(FileNotFoundError):
        io.copy_with_timestamp(tmp_path / "missing.txt", destinazione)


def test_write_json_scrive_newline_finale(tmp_path: Path) -> None:
    """Il file JSON deve terminare con newline per conformità stilistica."""

    destinazione = tmp_path / "dati.json"
    payload = {"a": 1, "b": [1, 2, 3]}
    risultato = io.write_json(payload, destinazione)
    assert risultato == destinazione
    contenuto = destinazione.read_text(encoding="utf-8")
    assert contenuto.endswith("\n")
    assert json.loads(contenuto) == payload


def test_write_json_crea_directory_intermedie(tmp_path: Path) -> None:
    """La serializzazione deve creare eventuali directory mancanti."""

    destinazione = tmp_path / "a" / "b" / "c.json"
    io.write_json({"chiave": "valore"}, destinazione)
    assert (tmp_path / "a" / "b").exists()
