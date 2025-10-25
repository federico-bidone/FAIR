"""Utility per proiettare matrici sul cono semidefinito positivo."""

from __future__ import annotations

import numpy as np


def project_to_psd(matrix: np.ndarray, eps: float | None = None) -> np.ndarray:
    """Proietta una matrice simmetrica sul cono PSD usando il metodo di Higham.

    L'algoritmo forza la simmetrizzazione dell'input, calcola autovalori e
    autovettori e tronca gli autovalori sotto una soglia minima ``eps``.
    L'eventuale ``eps`` mancante viene dedotto in modo robusto dalla diagonale
    per evitare matrici quasi-singolari prive di significato numerico.
    """

    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Input matrix must be square")

    # Simmetrizzazione esplicita per eliminare asimmetrie numeriche residue.
    matrix = 0.5 * (matrix + matrix.T)

    diag = np.diag(matrix)
    w, v = np.linalg.eigh(matrix)
    if eps is None:
        diag_mean = float(np.mean(diag)) if np.isfinite(np.mean(diag)) else 1.0
        eps = max(1e-8, 1e-6 * diag_mean)

    # Tronchiamo gli autovalori negativi per garantire la semidefinità positiva.
    w = np.maximum(w, eps)
    return (v * w) @ v.T


__all__ = ["project_to_psd"]
