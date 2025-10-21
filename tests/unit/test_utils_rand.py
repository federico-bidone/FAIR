from __future__ import annotations

from pathlib import Path

import numpy as np

from fair3.engine.utils import (
    DEFAULT_SEED,
    DEFAULT_STREAM,
    broadcast_seed,
    generator_from_seed,
    load_seeds,
    save_seeds,
    seed_for_stream,
    spawn_child_rng,
)


def test_load_seeds_defaults_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "audit" / "seeds.yml"
    seeds = load_seeds(path)
    assert seeds[DEFAULT_STREAM] == DEFAULT_SEED


def test_seed_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "audit" / "seeds.yml"
    save_seeds({"global": 123, "factors": 456}, path)
    seeds = load_seeds(path)
    assert seed_for_stream("factors", seeds=seeds) == 456
    assert seed_for_stream("unknown", seeds=seeds) == 123


def test_generator_from_seed_respects_int() -> None:
    rng = generator_from_seed(99)
    assert rng.integers(0, 100) == np.random.default_rng(99).integers(0, 100)


def test_broadcast_seed_sets_python_stack() -> None:
    rng = broadcast_seed(2024)
    assert rng.integers(0, 10) == np.random.default_rng(2024).integers(0, 10)


def test_spawn_child_rng_jumps_forward() -> None:
    parent = generator_from_seed(0)
    child = spawn_child_rng(parent, jumps=2)
    manual = np.random.Generator(parent.bit_generator.jumped(2))
    assert child.integers(0, 100) == manual.integers(0, 100)
