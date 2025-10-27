"""Validation utilities for FAIR-III configuration files.

This module intentionally avoids optional runtime dependencies such as
``pydantic`` so that the configuration validator remains available in minimal
environments.  The validation logic focuses on the configuration fields that
are consumed by the CLI and downstream pipelines.  Whenever an entry is
missing or invalid, the validator records human readable diagnostics while
returning the subset of sections that passed validation.
"""

from __future__ import annotations

# ruff: noqa: ANN401
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fair3.engine.utils.io import read_yaml

__all__ = ["ValidationSummary", "validate_configs"]


@dataclass(slots=True)
class ValidationSummary:
    """Aggregate structure returning validation diagnostics and parsed configs.

    Attributes:
      errors: Collection of error messages detected during schema validation.
      warnings: Soft diagnostics that highlight potential configuration issues.
      configs: Mapping between config label and the normalised payload obtained
        after validation.
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    configs: dict[str, dict[str, Any]] = field(default_factory=dict)


def _is_number(value: Any) -> bool:
    """Return ``True`` if ``value`` is a real number (excluding booleans)."""

    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_string(value: Any) -> bool:
    """Return ``True`` if ``value`` is a non-empty string."""

    return isinstance(value, str) and value.strip() != ""


def _as_float(
    value: Any,
    *,
    path: str,
    errors: list[str],
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    """Validate ``value`` as float returning the coerced number when valid."""

    if not _is_number(value):
        errors.append(f"{path} must be a number")
        return None
    number = float(value)
    if minimum is not None and number < minimum:
        errors.append(f"{path} must be >= {minimum}")
        return None
    if maximum is not None and number > maximum:
        errors.append(f"{path} must be <= {maximum}")
        return None
    return number


def _as_int(
    value: Any,
    *,
    path: str,
    errors: list[str],
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    """Validate ``value`` as integer returning the coerced number when valid."""

    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{path} must be an integer")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{path} must be >= {minimum}")
        return None
    if maximum is not None and value > maximum:
        errors.append(f"{path} must be <= {maximum}")
        return None
    return value


def _as_string(
    value: Any,
    *,
    path: str,
    errors: list[str],
    minimum_length: int | None = None,
    maximum_length: int | None = None,
) -> str | None:
    """Validate ``value`` as string returning the stripped text when valid."""

    if not _is_string(value):
        errors.append(f"{path} must be a non-empty string")
        return None
    text = value.strip()
    if minimum_length is not None and len(text) < minimum_length:
        errors.append(f"{path} must contain at least {minimum_length} characters")
        return None
    if maximum_length is not None and len(text) > maximum_length:
        errors.append(f"{path} must contain at most {maximum_length} characters")
        return None
    return text


def _normalise_str_list(
    value: Any,
    *,
    path: str,
    errors: list[str],
) -> list[str]:
    """Return a list of strings ensuring each entry is valid."""

    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return []
    items: list[str] = []
    for idx, entry in enumerate(value):
        text = _as_string(entry, path=f"{path}[{idx}]", errors=errors)
        if text is not None:
            items.append(text)
    return items


def _validate_contribution_plan(
    value: Any,
    *,
    errors: list[str],
) -> list[dict[str, Any]]:
    """Validate recurring contribution entries returning a normalised list."""

    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("household.contribution_plan must be a list")
        return []
    plan: list[dict[str, Any]] = []
    for idx, entry in enumerate(value):
        if not isinstance(entry, dict):
            errors.append(f"household.contribution_plan[{idx}] must be a mapping")
            continue
        start_year = _as_int(
            entry.get("start_year"),
            path=f"household.contribution_plan[{idx}].start_year",
            errors=errors,
            minimum=0,
        )
        end_year = _as_int(
            entry.get("end_year"),
            path=f"household.contribution_plan[{idx}].end_year",
            errors=errors,
            minimum=0,
        )
        amount = _as_float(
            entry.get("amount"),
            path=f"household.contribution_plan[{idx}].amount",
            errors=errors,
            minimum=0.0,
        )
        frequency = entry.get("frequency", "monthly")
        frequency_text = _as_string(
            frequency,
            path=f"household.contribution_plan[{idx}].frequency",
            errors=errors,
            minimum_length=1,
        )
        growth = _as_float(
            entry.get("growth", 0.0),
            path=f"household.contribution_plan[{idx}].growth",
            errors=errors,
            minimum=-1.0,
            maximum=1.0,
        )
        if (
            start_year is None
            or end_year is None
            or amount is None
            or frequency_text is None
            or growth is None
        ):
            continue
        if end_year < start_year:
            errors.append(f"household.contribution_plan[{idx}].end_year must be >= start_year")
            continue
        if frequency_text not in {"monthly", "lump_sum"}:
            errors.append(
                f"household.contribution_plan[{idx}].frequency must be 'monthly' or 'lump_sum'"
            )
            continue
        plan.append(
            {
                "start_year": start_year,
                "end_year": end_year,
                "amount": amount,
                "frequency": frequency_text,
                "growth": growth,
            }
        )
    return plan


def _validate_withdrawals(value: Any, *, errors: list[str]) -> list[dict[str, Any]]:
    """Validate household withdrawal entries returning the accepted list."""

    if value is None:
        return []
    if not isinstance(value, list):
        errors.append("household.withdrawals must be a list")
        return []
    withdrawals: list[dict[str, Any]] = []
    for idx, entry in enumerate(value):
        if not isinstance(entry, dict):
            errors.append(f"household.withdrawals[{idx}] must be a mapping")
            continue
        year = _as_int(
            entry.get("year"),
            path=f"household.withdrawals[{idx}].year",
            errors=errors,
            minimum=0,
        )
        amount = _as_float(
            entry.get("amount"),
            path=f"household.withdrawals[{idx}].amount",
            errors=errors,
            minimum=0.0,
        )
        if year is None or amount is None:
            continue
        if amount <= 0.0:
            errors.append(f"household.withdrawals[{idx}].amount must be > 0")
            continue
        withdrawals.append({"year": year, "amount": amount})
    return withdrawals


def _validate_filters(value: Any, *, errors: list[str]) -> dict[str, list[str]]:
    """Normalise instrument filter settings."""

    if value is None:
        return {"esg_exclusions": [], "allowed_instruments": []}
    if not isinstance(value, dict):
        errors.append("filters must be a mapping")
        return {"esg_exclusions": [], "allowed_instruments": []}
    return {
        "esg_exclusions": _normalise_str_list(
            value.get("esg_exclusions"), path="filters.esg_exclusions", errors=errors
        ),
        "allowed_instruments": _normalise_str_list(
            value.get("allowed_instruments"),
            path="filters.allowed_instruments",
            errors=errors,
        ),
    }


def _validate_household(value: Any, *, errors: list[str]) -> dict[str, Any] | None:
    """Validate the nested household configuration."""

    if not isinstance(value, dict):
        errors.append("household must be a mapping")
        return None
    investor = _as_string(
        value.get("investor", "household"),
        path="household.investor",
        errors=errors,
        minimum_length=1,
        maximum_length=64,
    )
    age = _as_int(value.get("age"), path="household.age", errors=errors, minimum=18, maximum=100)
    contrib_monthly = _as_float(
        value.get("contrib_monthly"),
        path="household.contrib_monthly",
        errors=errors,
        minimum=0.0,
    )
    horizon_years = _as_int(
        value.get("horizon_years"),
        path="household.horizon_years",
        errors=errors,
        minimum=1,
    )
    cvar_cap = _as_float(
        value.get("cvar_cap_1m"),
        path="household.cvar_cap_1m",
        errors=errors,
        minimum=0.0,
        maximum=1.0,
    )
    edar_cap = _as_float(
        value.get("edar_cap_3y"),
        path="household.edar_cap_3y",
        errors=errors,
        minimum=0.0,
        maximum=1.0,
    )
    initial_wealth = _as_float(
        value.get("initial_wealth", 0.0),
        path="household.initial_wealth",
        errors=errors,
        minimum=0.0,
    )
    contribution_growth = _as_float(
        value.get("contribution_growth", 0.02),
        path="household.contribution_growth",
        errors=errors,
        minimum=-1.0,
        maximum=1.0,
    )
    contribution_plan = _validate_contribution_plan(value.get("contribution_plan"), errors=errors)
    withdrawals = _validate_withdrawals(value.get("withdrawals"), errors=errors)

    if None in {
        investor,
        age,
        contrib_monthly,
        horizon_years,
        cvar_cap,
        edar_cap,
        initial_wealth,
        contribution_growth,
    }:
        return None

    return {
        "investor": investor,
        "age": age,
        "contrib_monthly": contrib_monthly,
        "horizon_years": horizon_years,
        "cvar_cap_1m": cvar_cap,
        "edar_cap_3y": edar_cap,
        "initial_wealth": initial_wealth,
        "contribution_growth": contribution_growth,
        "contribution_plan": contribution_plan,
        "withdrawals": withdrawals,
    }


def _validate_rebalancing(value: Any, *, errors: list[str]) -> dict[str, Any] | None:
    """Validate the rebalancing configuration block."""

    if not isinstance(value, dict):
        errors.append("rebalancing must be a mapping")
        return None
    frequency = _as_int(
        value.get("frequency_days"),
        path="rebalancing.frequency_days",
        errors=errors,
        minimum=1,
    )
    band = _as_float(
        value.get("no_trade_bands"),
        path="rebalancing.no_trade_bands",
        errors=errors,
        minimum=0.0,
        maximum=0.5,
    )
    if frequency is None or band is None:
        return None
    return {"frequency_days": frequency, "no_trade_bands": band}


def _validate_params_config(
    payload: dict[str, Any],
    *,
    summary: ValidationSummary,
) -> dict[str, Any] | None:
    """Validate the params YAML payload."""

    errors = summary.errors
    if not isinstance(payload, dict):
        errors.append("params must be a mapping")
        return None
    currency = _as_string(
        payload.get("currency_base"),
        path="params.currency_base",
        errors=errors,
        minimum_length=3,
        maximum_length=3,
    )
    filters = _validate_filters(payload.get("filters"), errors=errors)
    household = _validate_household(payload.get("household"), errors=errors)
    rebalancing = _validate_rebalancing(payload.get("rebalancing"), errors=errors)

    if currency is None or household is None or rebalancing is None:
        return None
    return {
        "currency_base": currency.upper(),
        "filters": filters,
        "household": household,
        "rebalancing": rebalancing,
    }


def _validate_tau(payload: Any, *, errors: list[str]) -> dict[str, float] | None:
    """Validate tau thresholds controlling statistical stability checks."""

    if not isinstance(payload, dict):
        errors.append("thresholds.tau must be a mapping")
        return None
    fields = {}
    for key in ("IR_view", "sigma_rel", "delta_rho", "beta_CI_width", "rc_tol"):
        number = _as_float(
            payload.get(key),
            path=f"thresholds.tau.{key}",
            errors=errors,
            minimum=0.0,
            maximum=1.0,
        )
        if number is None:
            return None
        fields[key] = number
    return fields


def _validate_execution(payload: Any, *, errors: list[str]) -> dict[str, float] | None:
    """Validate execution gating limits."""

    if not isinstance(payload, dict):
        errors.append("thresholds.execution must be a mapping")
        return None
    turnover = _as_float(
        payload.get("turnover_cap"),
        path="thresholds.execution.turnover_cap",
        errors=errors,
        minimum=0.0,
        maximum=1.0,
    )
    leverage = _as_float(
        payload.get("gross_leverage_cap"),
        path="thresholds.execution.gross_leverage_cap",
        errors=errors,
        minimum=1.0,
        maximum=5.0,
    )
    te_max = _as_float(
        payload.get("TE_max_factor"),
        path="thresholds.execution.TE_max_factor",
        errors=errors,
        minimum=0.0,
        maximum=0.5,
    )
    adv_cap = _as_float(
        payload.get("adv_cap_ratio"),
        path="thresholds.execution.adv_cap_ratio",
        errors=errors,
        minimum=0.0,
        maximum=1.0,
    )
    if None in {turnover, leverage, te_max, adv_cap}:
        return None
    return {
        "turnover_cap": turnover,
        "gross_leverage_cap": leverage,
        "TE_max_factor": te_max,
        "adv_cap_ratio": adv_cap,
    }


def _validate_regime_weights(payload: Any, *, errors: list[str]) -> dict[str, float]:
    """Validate or default the committee weights."""

    defaults = {"hmm": 0.5, "volatility": 0.3, "macro": 0.2}
    if payload is None:
        return defaults
    if not isinstance(payload, dict):
        errors.append("thresholds.regime.weights must be a mapping")
        return defaults
    weights: dict[str, float] = {}
    for key, default in defaults.items():
        number = payload.get(key, default)
        value = _as_float(
            number,
            path=f"thresholds.regime.weights.{key}",
            errors=errors,
            minimum=0.0,
        )
        if value is None:
            return defaults
        weights[key] = value
    if sum(weights.values()) <= 0.0:
        errors.append("thresholds.regime.weights must allocate positive mass")
        return defaults
    return weights


def _validate_regime_volatility(payload: Any, *, errors: list[str]) -> dict[str, int]:
    """Validate volatility configuration returning default values on errors."""

    defaults = {"window": 63, "min_duration": 5, "smoothing": 5}
    if payload is None:
        return defaults
    if not isinstance(payload, dict):
        errors.append("thresholds.regime.volatility must be a mapping")
        return defaults
    window = _as_int(
        payload.get("window", 63),
        path="thresholds.regime.volatility.window",
        errors=errors,
        minimum=5,
        maximum=252,
    )
    duration = _as_int(
        payload.get("min_duration", 5),
        path="thresholds.regime.volatility.min_duration",
        errors=errors,
        minimum=1,
        maximum=63,
    )
    smoothing = _as_int(
        payload.get("smoothing", 5),
        path="thresholds.regime.volatility.smoothing",
        errors=errors,
        minimum=1,
        maximum=63,
    )
    if None in {window, duration, smoothing}:
        return defaults
    return {"window": window, "min_duration": duration, "smoothing": smoothing}


def _validate_regime_macro(payload: Any, *, errors: list[str]) -> dict[str, Any]:
    """Validate macro trigger configuration returning default values on errors."""

    defaults = {
        "inflation_weight": 0.4,
        "pmi_weight": 0.35,
        "real_rate_weight": 0.25,
        "pmi_threshold": 50.0,
        "real_rate_threshold": 0.0,
        "smoothing": 3,
    }
    if payload is None:
        return defaults
    if not isinstance(payload, dict):
        errors.append("thresholds.regime.macro must be a mapping")
        return defaults
    inflation = _as_float(
        payload.get("inflation_weight", 0.4),
        path="thresholds.regime.macro.inflation_weight",
        errors=errors,
        minimum=0.0,
    )
    pmi = _as_float(
        payload.get("pmi_weight", 0.35),
        path="thresholds.regime.macro.pmi_weight",
        errors=errors,
        minimum=0.0,
    )
    real_rate = _as_float(
        payload.get("real_rate_weight", 0.25),
        path="thresholds.regime.macro.real_rate_weight",
        errors=errors,
        minimum=0.0,
    )
    pmi_threshold = _as_float(
        payload.get("pmi_threshold", 50.0),
        path="thresholds.regime.macro.pmi_threshold",
        errors=errors,
    )
    real_rate_threshold = _as_float(
        payload.get("real_rate_threshold", 0.0),
        path="thresholds.regime.macro.real_rate_threshold",
        errors=errors,
    )
    smoothing = _as_int(
        payload.get("smoothing", 3),
        path="thresholds.regime.macro.smoothing",
        errors=errors,
        minimum=1,
        maximum=12,
    )
    if None in {inflation, pmi, real_rate, pmi_threshold, real_rate_threshold, smoothing}:
        return defaults
    if inflation + pmi + real_rate <= 0.0:
        errors.append("thresholds.regime.macro weights must sum to a positive value")
        return defaults
    return {
        "inflation_weight": inflation,
        "pmi_weight": pmi,
        "real_rate_weight": real_rate,
        "pmi_threshold": pmi_threshold,
        "real_rate_threshold": real_rate_threshold,
        "smoothing": smoothing,
    }


def _validate_regime(payload: Any, *, errors: list[str]) -> dict[str, Any] | None:
    """Validate regime hysteresis settings."""

    if not isinstance(payload, dict):
        errors.append("thresholds.regime must be a mapping")
        return None
    on = _as_float(
        payload.get("on"),
        path="thresholds.regime.on",
        errors=errors,
        minimum=0.0,
        maximum=1.0,
    )
    off = _as_float(
        payload.get("off"),
        path="thresholds.regime.off",
        errors=errors,
        minimum=0.0,
        maximum=1.0,
    )
    dwell = _as_int(
        payload.get("dwell_days"),
        path="thresholds.regime.dwell_days",
        errors=errors,
        minimum=1,
        maximum=252,
    )
    cooldown = _as_int(
        payload.get("cooldown_days"),
        path="thresholds.regime.cooldown_days",
        errors=errors,
        minimum=0,
        maximum=252,
    )
    activate = _as_int(
        payload.get("activate_streak", 3),
        path="thresholds.regime.activate_streak",
        errors=errors,
        minimum=1,
        maximum=10,
    )
    deactivate = _as_int(
        payload.get("deactivate_streak", 3),
        path="thresholds.regime.deactivate_streak",
        errors=errors,
        minimum=1,
        maximum=10,
    )
    weights = _validate_regime_weights(payload.get("weights"), errors=errors)
    volatility = _validate_regime_volatility(payload.get("volatility"), errors=errors)
    macro = _validate_regime_macro(payload.get("macro"), errors=errors)

    if None in {on, off, dwell, cooldown, activate, deactivate}:
        return None
    if on <= off:
        errors.append("thresholds.regime.on must be greater than thresholds.regime.off")
        return None
    return {
        "on": on,
        "off": off,
        "dwell_days": dwell,
        "cooldown_days": cooldown,
        "activate_streak": activate,
        "deactivate_streak": deactivate,
        "weights": weights,
        "volatility": volatility,
        "macro": macro,
    }


def _validate_drift(payload: Any, *, errors: list[str]) -> dict[str, float] | None:
    """Validate drift-based tolerance bands."""

    if not isinstance(payload, dict):
        errors.append("thresholds.drift must be a mapping")
        return None
    weight_tol = _as_float(
        payload.get("weight_tol"),
        path="thresholds.drift.weight_tol",
        errors=errors,
        minimum=0.0,
        maximum=0.5,
    )
    rc_tol = _as_float(
        payload.get("rc_tol"),
        path="thresholds.drift.rc_tol",
        errors=errors,
        minimum=0.0,
        maximum=0.5,
    )
    if None in {weight_tol, rc_tol}:
        return None
    return {"weight_tol": weight_tol, "rc_tol": rc_tol}


def _validate_thresholds_config(
    payload: dict[str, Any],
    *,
    summary: ValidationSummary,
) -> dict[str, Any] | None:
    """Validate thresholds YAML payload."""

    errors = summary.errors
    if not isinstance(payload, dict):
        errors.append("thresholds must be a mapping")
        return None
    vol_target = _as_float(
        payload.get("vol_target_annual"),
        path="thresholds.vol_target_annual",
        errors=errors,
        minimum=0.01,
        maximum=0.5,
    )
    tau = _validate_tau(payload.get("tau"), errors=errors)
    execution = _validate_execution(payload.get("execution"), errors=errors)
    regime = _validate_regime(payload.get("regime"), errors=errors)
    drift = _validate_drift(payload.get("drift"), errors=errors)

    if vol_target is None or tau is None or execution is None or regime is None or drift is None:
        return None
    return {
        "vol_target_annual": vol_target,
        "tau": tau,
        "execution": execution,
        "regime": regime,
        "drift": drift,
    }


def _validate_goals(payload: Any, *, errors: list[str]) -> list[dict[str, Any]] | None:
    """Validate the list of household goals."""

    if not isinstance(payload, list):
        errors.append("goals.goals must be a list")
        return None
    goals: list[dict[str, Any]] = []
    for idx, entry in enumerate(payload):
        if not isinstance(entry, dict):
            errors.append(f"goals.goals[{idx}] must be a mapping")
            continue
        name = _as_string(
            entry.get("name"),
            path=f"goals.goals[{idx}].name",
            errors=errors,
            minimum_length=1,
        )
        wealth = _as_float(
            entry.get("W"),
            path=f"goals.goals[{idx}].W",
            errors=errors,
            minimum=0.0,
        )
        horizon = _as_int(
            entry.get("T_years"),
            path=f"goals.goals[{idx}].T_years",
            errors=errors,
            minimum=1,
        )
        p_min = _as_float(
            entry.get("p_min"),
            path=f"goals.goals[{idx}].p_min",
            errors=errors,
            minimum=0.0,
            maximum=1.0,
        )
        weight = _as_float(
            entry.get("weight", 1.0),
            path=f"goals.goals[{idx}].weight",
            errors=errors,
            minimum=0.0,
            maximum=1.0,
        )
        if None in {name, wealth, horizon, p_min, weight}:
            continue
        goals.append(
            {
                "name": name,
                "W": wealth,
                "T_years": horizon,
                "p_min": p_min,
                "weight": weight,
            }
        )
    if not goals:
        errors.append("goals.goals must contain at least one entry")
        return None
    return goals


def _validate_goals_config(
    payload: dict[str, Any],
    *,
    summary: ValidationSummary,
) -> dict[str, Any] | None:
    """Validate goals YAML payload."""

    errors = summary.errors
    if not isinstance(payload, dict):
        errors.append("goals must be a mapping")
        return None
    goals = _validate_goals(payload.get("goals"), errors=errors)
    if goals is None:
        return None
    return {"goals": goals}


def _load_payload(
    label: str,
    path: Path,
    *,
    summary: ValidationSummary,
) -> dict[str, Any] | None:
    """Load YAML payload handling missing files and empty documents."""

    if not path.exists():
        summary.errors.append(f"{label}: missing file at {path}")
        return None
    payload = read_yaml(path)
    if payload is None:
        summary.errors.append(f"{label}: file at {path} is empty")
        return None
    if not isinstance(payload, dict):
        summary.errors.append(f"{label}: expected a mapping at {path}")
        return None
    return payload


def validate_configs(
    *,
    params_path: Path | str = Path("configs") / "params.yml",
    thresholds_path: Path | str = Path("configs") / "thresholds.yml",
    goals_path: Path | str = Path("configs") / "goals.yml",
) -> ValidationSummary:
    """Validate FAIR-III YAML configuration files and return diagnostics."""

    summary = ValidationSummary()

    params_payload = _load_payload("params", Path(params_path), summary=summary)
    if params_payload is not None:
        error_count = len(summary.errors)
        params = _validate_params_config(params_payload, summary=summary)
        if params is not None and len(summary.errors) == error_count:
            summary.configs["params"] = params

    thresholds_payload = _load_payload("thresholds", Path(thresholds_path), summary=summary)
    if thresholds_payload is not None:
        error_count = len(summary.errors)
        thresholds = _validate_thresholds_config(thresholds_payload, summary=summary)
        if thresholds is not None and len(summary.errors) == error_count:
            summary.configs["thresholds"] = thresholds

    goals_payload = _load_payload("goals", Path(goals_path), summary=summary)
    if goals_payload is not None:
        error_count = len(summary.errors)
        goals = _validate_goals_config(goals_payload, summary=summary)
        if goals is not None and len(summary.errors) == error_count:
            summary.configs["goals"] = goals

    goals_config = summary.configs.get("goals", {}).get("goals", [])
    if goals_config:
        total_weight = sum(goal.get("weight", 0.0) for goal in goals_config)
        if abs(total_weight - 1.0) > 0.05:
            summary.warnings.append(
                f"goals.weights: sum is {total_weight:.3f}; consider normalising to 1.0"
            )

    thresholds_config = summary.configs.get("thresholds")
    if thresholds_config:
        drift = thresholds_config.get("drift", {})
        weight_tol = drift.get("weight_tol")
        rc_tol = drift.get("rc_tol")
        if weight_tol is not None and rc_tol is not None and weight_tol < rc_tol / 2.0:
            summary.warnings.append(
                "drift: weight tolerance is much tighter than risk contribution tolerance"
            )
        weights = thresholds_config.get("regime", {}).get("weights", {})
        weight_sum = sum(weights.get(key, 0.0) for key in ("hmm", "volatility", "macro"))
        if weight_sum > 0.0 and abs(weight_sum - 1.0) > 0.25:
            summary.warnings.append(
                f"regime.weights: sum is {weight_sum:.3f}; consider normalising to 1.0"
            )
        macro = thresholds_config.get("regime", {}).get("macro", {})
        macro_sum = sum(
            macro.get(key, 0.0) for key in ("inflation_weight", "pmi_weight", "real_rate_weight")
        )
        if macro_sum <= 0.0:
            summary.warnings.append("regime.macro: at least one macro weight must be positive")

    return summary
