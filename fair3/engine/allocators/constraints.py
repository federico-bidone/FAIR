"""Diagnostica dei vincoli per i motori di allocazione."""

from __future__ import annotations

import numpy as np

from .erc import risk_contributions


def erc_cluster_violation(
    w: np.ndarray,
    Sigma: np.ndarray,  # noqa: N803
    clusters: list[list[int]],
    tol: float,  # noqa: N803
) -> float:
    """Restituisce la deviazione ERC dei cluster al netto della tolleranza.

    Valori negativi indicano che la deviazione rientra nella fascia di tolleranza
    accettabile. L'helper funziona con cluster irregolari e ignora in modo
    trasparente quelli vuoti.
    """

    if not clusters:
        return -tol

    rc = risk_contributions(np.asarray(w, dtype=float), np.asarray(Sigma, dtype=float))
    totals = []
    for idx in clusters:
        if not idx:
            continue
        idx_arr = np.asarray(idx, dtype=int)
        totals.append(float(np.sum(rc[idx_arr])))
    if not totals:
        return -tol
    target = float(np.mean(totals))
    deviation = max(abs(t - target) for t in totals)
    return deviation - float(tol)
