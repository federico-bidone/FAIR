"""Verifiche di sanità per le pipeline verbose."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fair3.engine.utils.logging as logging_utils
from fair3.engine.allocators import pipeline as alloc_pipeline
from fair3.engine.estimates import pipeline as est_pipeline
from fair3.engine.utils.logging import get_stream_logger


def test_get_stream_logger_respects_environment(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Il logger deve rispettare livello e formato configurati."""

    monkeypatch.setenv("FAIR_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("FAIR_LOG_FORMAT", "%(levelname)s:%(name)s:%(message)s")
    logging_utils._determine_level.cache_clear()
    logging_utils._determine_format.cache_clear()
    logger = get_stream_logger("fair3.tests.logging")

    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert logging_utils._determine_level() == logging.DEBUG
    assert logging_utils._determine_format() == "%(levelname)s:%(name)s:%(message)s"

    with caplog.at_level("DEBUG", logger=logger.name):
        logger.debug("hello world")
    assert "hello world" in caplog.text


def _patch_optimisation_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    factors = pd.DataFrame(
        [[0.01, 0.02], [0.02, 0.01]],
        columns=["A", "B"],
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )
    mu = pd.Series([0.01, 0.02], index=["A", "B"], name="mu_post")
    sigma = np.array([[0.1, 0.02], [0.02, 0.2]])

    monkeypatch.setattr(alloc_pipeline, "_load_mu_sigma", lambda *_: (mu, sigma))
    monkeypatch.setattr(alloc_pipeline, "_load_factors", lambda *_: factors)
    monkeypatch.setattr(alloc_pipeline, "_load_configs", lambda *_, **__: ({}, {}))
    monkeypatch.setattr(alloc_pipeline, "run_audit_snapshot", lambda **_: {})


def test_run_optimization_pipeline_requires_generators(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Viene sollevato un errore esplicito senza generatori richiesti."""

    _patch_optimisation_inputs(monkeypatch)
    with pytest.raises(ValueError, match="almeno un generatore"):
        alloc_pipeline.run_optimization_pipeline(
            artifacts_root=tmp_path,
            params_path=tmp_path / "params.yml",
            thresholds_path=tmp_path / "thresholds.yml",
            config_paths=(),
            audit_dir=tmp_path / "audit",
            seed_path=tmp_path / "seed.yml",
            generators=(),
            use_meta=False,
        )


def test_run_optimization_pipeline_emits_verbose_logs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """La pipeline di ottimizzazione deve loggare i passaggi chiave."""

    _patch_optimisation_inputs(monkeypatch)
    caplog.set_level("INFO")
    result = alloc_pipeline.run_optimization_pipeline(
        artifacts_root=tmp_path,
        params_path=tmp_path / "params.yml",
        thresholds_path=tmp_path / "thresholds.yml",
        config_paths=(),
        audit_dir=tmp_path / "audit",
        seed_path=tmp_path / "seed.yml",
        generators=("B",),
        use_meta=False,
    )

    assert result.allocation_path.exists()
    assert result.diagnostics_path.exists()
    assert "Avvio della pipeline di ottimizzazione" in caplog.text
    assert "Allocazione finale salvata" in caplog.text


def _patch_estimate_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    factors = pd.DataFrame(
        [[0.1, 0.2], [0.0, 0.3], [-0.1, 0.1]],
        columns=["A", "B"],
        index=pd.date_range("2024-01-01", periods=3, freq="D"),
    )
    thresholds = {"tau": {"IR_view": 0.2}, "vol_target_annual": 0.1}

    monkeypatch.setattr(est_pipeline, "_load_factors", lambda *_: factors)
    monkeypatch.setattr(est_pipeline, "_load_thresholds", lambda *_: thresholds)
    monkeypatch.setattr(est_pipeline, "_append_drift_log", lambda path, *_: path)
    monkeypatch.setattr(est_pipeline, "run_audit_snapshot", lambda **_: {})


def test_run_estimate_pipeline_creates_expected_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """La pipeline di stima salva gli artefatti e spiega il blending."""

    _patch_estimate_inputs(monkeypatch)
    caplog.set_level("INFO")
    result = est_pipeline.run_estimate_pipeline(
        artifacts_root=tmp_path,
        thresholds_path=tmp_path / "thresholds.yml",
        config_paths=(),
        audit_dir=tmp_path / "audit",
        seed_path=tmp_path / "seed.yml",
        cv_splits=2,
        seed=1,
    )

    assert result.mu_post_path.exists()
    assert result.sigma_path.exists()
    assert "Blending con omega" in caplog.text
