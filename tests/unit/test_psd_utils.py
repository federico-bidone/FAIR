"""Test dedicati alla proiezione PSD del modulo ``psd``."""

from __future__ import annotations

import numpy as np
import pytest

from fair3.engine.utils.psd import project_to_psd


def test_project_to_psd_rende_matrice_semidefinita() -> None:
    """La proiezione deve annullare gli autovalori negativi."""

    matrice = np.array([[2.0, -3.0], [-3.0, 5.0]])
    proiettata = project_to_psd(matrice)

    autovalori = np.linalg.eigvalsh(proiettata)
    assert np.all(autovalori >= 0.0)


def test_project_to_psd_rispetta_eps_personalizzato() -> None:
    """Un ``eps`` esplicito deve troncare l'autovalore minimo a quella soglia."""

    matrice = np.array([[1e-9, 0.0], [0.0, 1e-9]])
    proiettata = project_to_psd(matrice, eps=1e-4)

    autovalori = np.linalg.eigvalsh(proiettata)
    assert pytest.approx(1e-4, rel=1e-6) == autovalori.min()


def test_project_to_psd_rifiuta_matrici_non_quadrate() -> None:
    """Le matrici rettangolari devono generare un ``ValueError`` descrittivo."""

    with pytest.raises(ValueError) as exc:
        project_to_psd(np.zeros((2, 3)))

    assert "square" in str(exc.value)
