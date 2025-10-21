"""Positive semidefinite projection utilities."""

from __future__ import annotations

import numpy as np


def project_to_psd(matrix: np.ndarray, eps: float | None = None) -> np.ndarray:
    """Project a symmetric matrix onto the PSD cone using Higham's method.

    The implementation mirrors the reference snippet in the FAIR-III specification
    and enforces a minimum eigenvalue ``eps`` derived from the matrix diagonal when
    it is not provided explicitly.
    """

    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("Input matrix must be square")
    matrix = 0.5 * (matrix + matrix.T)
    diag = np.diag(matrix)
    w, v = np.linalg.eigh(matrix)
    if eps is None:
        diag_mean = float(np.mean(diag)) if np.isfinite(np.mean(diag)) else 1.0
        eps = max(1e-8, 1e-6 * diag_mean)
    w = np.maximum(w, eps)
    return (v * w) @ v.T


__all__ = ["project_to_psd"]
