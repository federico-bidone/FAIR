"""Validation command tests covering schema and CLI integration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from fair3.cli.main import main as cli_main
from fair3.engine.validate import ValidationSummary, validate_configs


def _write_yaml(path: Path, payload: dict[str, object]) -> Path:
    """Serialize ``payload`` to ``path`` using UTF-8 encoding."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=True), encoding="utf-8")
    return path


def _seed_valid_configs(root: Path) -> tuple[Path, Path, Path]:
    """Create sample configuration files returning their respective paths."""

    params = {
        "currency_base": "EUR",
        "household": {
            "age": 35,
            "contrib_monthly": 500.0,
            "horizon_years": 25,
            "cvar_cap_1m": 0.12,
            "edar_cap_3y": 0.25,
            "initial_wealth": 10_000.0,
            "contribution_growth": 0.02,
        },
        "filters": {
            "esg_exclusions": ["controversial_weapons"],
            "allowed_instruments": ["UCITS_ETF", "CASH"],
        },
        "rebalancing": {"frequency_days": 30, "no_trade_bands": 0.03},
    }
    thresholds = {
        "vol_target_annual": 0.11,
        "tau": {
            "IR_view": 0.15,
            "sigma_rel": 0.2,
            "delta_rho": 0.15,
            "beta_CI_width": 0.25,
            "rc_tol": 0.02,
        },
        "execution": {
            "turnover_cap": 0.4,
            "gross_leverage_cap": 1.75,
            "TE_max_factor": 0.02,
            "adv_cap_ratio": 0.05,
        },
        "regime": {
            "on": 0.65,
            "off": 0.45,
            "dwell_days": 20,
            "cooldown_days": 10,
            "activate_streak": 3,
            "deactivate_streak": 3,
            "weights": {"hmm": 0.5, "volatility": 0.3, "macro": 0.2},
            "volatility": {"window": 63, "min_duration": 5, "smoothing": 5},
            "macro": {
                "inflation_weight": 0.4,
                "pmi_weight": 0.35,
                "real_rate_weight": 0.25,
                "pmi_threshold": 50.0,
                "real_rate_threshold": 0.0,
                "smoothing": 3,
            },
        },
        "drift": {"weight_tol": 0.03, "rc_tol": 0.05},
    }
    goals = {
        "goals": [
            {"name": "pensione", "W": 300_000.0, "T_years": 30, "p_min": 0.8, "weight": 0.7},
            {"name": "casa", "W": 100_000.0, "T_years": 8, "p_min": 0.7, "weight": 0.3},
        ]
    }
    params_path = _write_yaml(root / "params.yml", params)
    thresholds_path = _write_yaml(root / "thresholds.yml", thresholds)
    goals_path = _write_yaml(root / "goals.yml", goals)
    return params_path, thresholds_path, goals_path


def test_validate_configs_reports_success(tmp_path: Path) -> None:
    """The validator returns a populated summary without errors for valid inputs."""

    params_path, thresholds_path, goals_path = _seed_valid_configs(tmp_path)
    summary = validate_configs(
        params_path=params_path,
        thresholds_path=thresholds_path,
        goals_path=goals_path,
    )
    assert isinstance(summary, ValidationSummary)
    assert not summary.errors
    assert "params" in summary.configs
    assert summary.configs["params"]["currency_base"] == "EUR"
    assert summary.warnings == []


def test_validate_configs_reports_schema_errors(tmp_path: Path) -> None:
    """Invalid thresholds surface human readable error messages."""

    params_path, _, goals_path = _seed_valid_configs(tmp_path)
    invalid_thresholds = {
        "vol_target_annual": 0.09,
        "tau": {
            "IR_view": 0.2,
            "sigma_rel": 0.4,
            "delta_rho": 0.3,
            "beta_CI_width": 0.2,
            "rc_tol": 0.05,
        },
        "execution": {
            "turnover_cap": 0.5,
            "gross_leverage_cap": 1.5,
            "TE_max_factor": 0.05,
            "adv_cap_ratio": 0.1,
        },
        "regime": {"on": 0.40, "off": 0.45, "dwell_days": 5, "cooldown_days": 2},
        "drift": {"weight_tol": 0.02, "rc_tol": 0.03},
    }
    thresholds_path = _write_yaml(tmp_path / "thresholds_invalid.yml", invalid_thresholds)
    summary = validate_configs(
        params_path=params_path,
        thresholds_path=thresholds_path,
        goals_path=goals_path,
    )
    assert summary.errors
    assert any("regime.on" in error for error in summary.errors)


def test_cli_validate_verbose_prints_payload(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI outputs verbose payloads and success status when validation passes."""

    params_path, thresholds_path, goals_path = _seed_valid_configs(tmp_path)
    cli_main(
        [
            "validate",
            "--params",
            str(params_path),
            "--thresholds",
            str(thresholds_path),
            "--goals",
            str(goals_path),
            "--verbose",
        ]
    )
    captured = capsys.readouterr()
    assert "[fair3] validate status=ok" in captured.out
    assert "currency_base" in captured.out
    assert captured.err == ""
