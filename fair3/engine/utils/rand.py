"""Gestione centralizzata dei seed casuali per l'engine FAIR-III."""

from __future__ import annotations

import random
from collections.abc import Mapping
from pathlib import Path

import numpy as np
import yaml

DEFAULT_STREAM = "global"
DEFAULT_SEED = 42
DEFAULT_SEED_PATH = Path("audit") / "seeds.yml"

__all__ = [
    "DEFAULT_SEED",
    "DEFAULT_SEED_PATH",
    "DEFAULT_STREAM",
    "load_seeds",
    "save_seeds",
    "seed_for_stream",
    "generator_from_seed",
    "broadcast_seed",
    "spawn_child_rng",
]


def load_seeds(seed_path: Path | str = DEFAULT_SEED_PATH) -> dict[str, int]:
    """Carica il dizionario dei seed dal percorso indicato.

    La funzione supporta file non ancora creati restituendo sempre almeno lo
    stream ``global`` con il seed di default, così che la pipeline resti
    deterministica sin dal primo avvio.
    """

    path = Path(seed_path)
    if not path.exists():
        return {DEFAULT_STREAM: DEFAULT_SEED}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if isinstance(data, dict) and "seeds" in data and isinstance(data["seeds"], dict):
        seeds_section = data["seeds"]
    elif isinstance(data, dict):
        seeds_section = data
    else:
        raise TypeError("Seed file must contain a mapping of stream -> seed")

    seeds: dict[str, int] = {}
    for key, value in seeds_section.items():
        if value is None:
            continue
        seeds[str(key)] = int(value)

    seeds.setdefault(DEFAULT_STREAM, DEFAULT_SEED)
    return seeds


def save_seeds(
    seeds: Mapping[str, int],
    seed_path: Path | str = DEFAULT_SEED_PATH,
) -> Path:
    """Salva su disco una mappatura ``stream -> seed`` normalizzata."""

    path = Path(seed_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"seeds": {str(k): int(v) for k, v in seeds.items()}}
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=True)
    return path


def seed_for_stream(
    stream: str = DEFAULT_STREAM,
    *,
    seeds: Mapping[str, int] | None = None,
    seed_path: Path | str = DEFAULT_SEED_PATH,
) -> int:
    """Ricava il seed per ``stream`` usando la mappatura fornita o il file."""

    seeds_dict = dict(seeds) if seeds is not None else load_seeds(seed_path)
    if DEFAULT_STREAM not in seeds_dict:
        seeds_dict[DEFAULT_STREAM] = DEFAULT_SEED
    return int(seeds_dict.get(stream, seeds_dict[DEFAULT_STREAM]))


def generator_from_seed(
    seed: int | np.random.Generator | None = None,
    *,
    stream: str = DEFAULT_STREAM,
    seeds: Mapping[str, int] | None = None,
    seed_path: Path | str = DEFAULT_SEED_PATH,
) -> np.random.Generator:
    """Restituisce un generatore NumPy coerente con lo stream richiesto."""

    if isinstance(seed, np.random.Generator):
        return seed
    if seed is not None:
        resolved_seed = seed
    else:
        resolved_seed = seed_for_stream(stream, seeds=seeds, seed_path=seed_path)
    return np.random.default_rng(int(resolved_seed))


def broadcast_seed(seed: int) -> np.random.Generator:
    """Applica il seed sia al RNG di Python che a NumPy restituendo il generatore."""

    random.seed(seed)
    np.random.seed(seed)
    return np.random.default_rng(seed)


def spawn_child_rng(
    parent: np.random.Generator,
    *,
    jumps: int = 1,
) -> np.random.Generator:
    """Genera un RNG figlio deterministico eseguendo salti controllati."""

    if jumps < 1:
        raise ValueError("jumps must be >= 1")

    # L'API ``jumped`` garantisce sequenze disgiunte replicabili tra i worker.
    jumped = parent.bit_generator.jumped(jumps)
    return np.random.Generator(jumped)
