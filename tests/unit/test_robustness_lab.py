"""Suite di test per il laboratorio di robustezza con messaggi in italiano."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fair3.engine.robustness import (
    DEFAULT_FEATURES,
    RobustnessConfig,
    block_bootstrap_metrics,
    replay_shocks,
    run_ablation_study,
    run_robustness_lab,
)


def test_block_bootstrap_metrics_deterministico() -> None:
    """Verifica che il bootstrap produca risultati deterministici con seed fisso."""

    returns = pd.Series(np.full(120, 0.002, dtype="float64"))
    metrics, gates = block_bootstrap_metrics(
        returns,
        block_size=12,
        draws=32,
        cagr_target=-0.01,
        max_drawdown_threshold=-0.50,
        seed=123,
    )
    assert len(metrics) == 32
    assert np.isclose(metrics["max_drawdown"].std(ddof=0), 0.0)
    assert {"sharpe", "cvar", "edar"}.issubset(metrics.columns)
    assert gates.exceedance_probability == 0.0
    assert gates.passes()


def test_block_bootstrap_metrics_errori_input() -> None:
    """I messaggi di errore devono spiegare chiaramente i problemi di input."""

    with pytest.raises(ValueError, match="returns deve contenere"):
        block_bootstrap_metrics([], block_size=12)
    with pytest.raises(ValueError, match="block_size deve essere >= 1"):
        block_bootstrap_metrics([0.01], block_size=0)
    with pytest.raises(ValueError, match="non può superare"):
        block_bootstrap_metrics([0.01, 0.02], block_size=10)


def test_run_ablation_study_gestione_flag() -> None:
    """L'ablation deve rispettare i flag base e mantenere le metriche coerenti."""

    chiamate: list[dict[str, bool]] = []

    def runner(flags: dict[str, bool]) -> dict[str, float]:
        chiamate.append(flags)
        return {"sharpe": 0.5 if flags["sigma_psd"] else 0.4}

    outcome = run_ablation_study(
        runner,
        features=("sigma_psd",),
        base_flags={"sigma_psd": False},
    )
    assert len(chiamate) == 2
    baseline, variante = chiamate
    assert baseline == {"sigma_psd": False}
    assert variante == {"sigma_psd": False}
    assert np.allclose(outcome.table["delta"].to_numpy(), 0.0)


def test_run_ablation_study_errori() -> None:
    """Vengono lanciati errori descrittivi per casi limite noti."""

    def vuoto(_: dict[str, bool]) -> dict[str, float]:
        return {}

    with pytest.raises(ValueError, match="almeno un elemento"):
        run_ablation_study(lambda _: {"x": 1.0}, features=())
    with pytest.raises(ValueError, match="almeno una metrica"):
        run_ablation_study(vuoto, features=("x",))

    with pytest.raises(ValueError, match="stessi nomi di metrica"):
        run_ablation_study(
            lambda flags: {"b": 2.0} if not flags["x"] else {"a": 1.0},
            features=("x",),
        )


def test_replay_shocks_input_vuoto() -> None:
    """Gli shock richiedono almeno un rendimento di base."""

    with pytest.raises(ValueError, match="base_returns deve contenere"):
        replay_shocks([])


def test_replay_shocks_scaling(tmp_path: Path) -> None:
    """Gli shock scalati devono gestire correttamente la volatilità nulla."""

    base_returns = np.zeros(128)
    frame = replay_shocks(base_returns, scale_to_base_vol=True)
    assert (frame["max_drawdown"] == 0.0).all()
    assert (frame["cagr"] == 0.0).all()

    # Scriviamo un CSV per verificare la compatibilità con i workflow reali.
    destinazione = tmp_path / "scenari.csv"
    frame.to_csv(destinazione, index=False)
    assert destinazione.exists()


def test_run_robustness_lab_generates_artifacts(tmp_path: Path) -> None:
    """Il laboratorio produce file e riepiloghi auditabili."""

    returns = pd.Series(np.linspace(-0.01, 0.02, num=180))
    config = RobustnessConfig(draws=32, block_size=20, output_dir=tmp_path)

    def runner(flags: dict[str, bool], seed: int | None = None) -> dict[str, float]:
        scala = 1.0 if flags.get("bl_fallback", True) else 0.8
        rng = np.random.default_rng(seed)
        simulato = rng.normal(0.005 * scala, 0.01, size=64)
        sharpe = float(np.mean(simulato) / np.std(simulato, ddof=0))
        return {"sharpe": sharpe, "max_drawdown": float(np.min(simulato.cumsum()))}

    artifacts, gates = run_robustness_lab(
        returns,
        config=config,
        seed=21,
        ablation_runner=runner,
        base_flags={"bl_fallback": True, "nuovo_flag": False},
    )
    for path in (
        artifacts.bootstrap_csv,
        artifacts.scenarios_csv,
        artifacts.summary_json,
        artifacts.report_pdf,
        artifacts.ablation_csv,
    ):
        assert path is not None and path.exists()

    payload = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))
    assert set(payload) == {
        "max_drawdown_threshold",
        "cagr_target",
        "exceedance_probability",
        "cagr_lower_bound",
        "alpha",
        "passes",
    }
    assert isinstance(gates.passes(), bool)


def test_run_robustness_lab_senza_ablation(tmp_path: Path) -> None:
    """È possibile eseguire il laboratorio senza fornire un runner di ablation."""

    returns = pd.Series(np.linspace(-0.01, 0.02, num=90))
    config = RobustnessConfig(draws=8, block_size=10, output_dir=tmp_path)

    artifacts, gates = run_robustness_lab(returns, config=config, seed=5)
    assert artifacts.ablation_csv is None
    assert artifacts.bootstrap_csv.exists()
    assert artifacts.scenarios_csv.exists()
    assert isinstance(gates.passes(), bool)


@pytest.mark.parametrize(
    "feature_lista",
    [DEFAULT_FEATURES, ("singola",)],
)
def test_run_ablation_study_percorre_tutte_le_feature(feature_lista: tuple[str, ...]) -> None:
    """Ogni feature deve essere disattivata una volta, mantenendo ordine e delta."""

    invocazioni: list[dict[str, bool]] = []

    def runner(flags: dict[str, bool]) -> dict[str, float]:
        invocazioni.append(flags)
        return {"metrica": float(sum(flags.values()))}

    outcome = run_ablation_study(runner, features=feature_lista)
    # 1 baseline + una variante per ogni feature.
    assert len(invocazioni) == len(feature_lista) + 1
    assert list(outcome.table["feature"]) == list(feature_lista)
    assert outcome.table["delta"].isin([0.0, -1.0, 1.0]).all()
