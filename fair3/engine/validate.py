"""Configuration validation utilities for CLI pre-flight checks.

This module centralises schema validation for the primary configuration files used by the
FAIR-III engine. Each validation step relies on pydantic models so that errors are precise
and can be surfaced directly to the caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from fair3.engine.utils.io import read_yaml


@dataclass(slots=True)
class ValidationSummary:
    """Aggregate structure returning validation diagnostics and parsed configs.

    Attributes:
      errors: Collection of error messages detected during schema validation.
      warnings: Collection of warning messages that highlight soft issues such as
        imbalanced weights.
      configs: Mapping between config label and the normalised payload obtained after
        validation. The payloads can be reused when --verbose is enabled to display the
        parsed structures to the user.
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    configs: dict[str, dict[str, Any]] = field(default_factory=dict)


class FiltersConfig(BaseModel):
    """Schema enforcing instrument filters applied at ingest or allocation time.

    Attributes:
      esg_exclusions: List of textual ESG exclusion labels.
      allowed_instruments: List of instrument categories that remain eligible.
    """

    model_config = ConfigDict(extra="forbid")

    esg_exclusions: list[str] = Field(default_factory=list)
    allowed_instruments: list[str] = Field(default_factory=list)


class RebalancingConfig(BaseModel):
    """Schema for tactical rebalancing settings.

    Attributes:
      frequency_days: Number of days between rebalancing checkpoints.
      no_trade_bands: Symmetric tolerance band applied to portfolio weights.
    """

    model_config = ConfigDict(extra="forbid")

    frequency_days: int = Field(..., ge=1, description="Cadence in days for rebalancing")
    no_trade_bands: float = Field(
        ..., ge=0.0, le=0.5, description="Absolute tolerance applied before rebalancing"
    )


class ContributionEventConfig(BaseModel):
    """Recurring or lump-sum contribution applied to the cash-flow plan.

    Attributes:
      start_year: First relative calendar year covered by the rule.
      end_year: Last relative calendar year included in the rule.
      amount: Contribution amount expressed in euros per frequency unit.
      frequency: Either ``monthly`` or ``lump_sum`` contributions.
      growth: Optional annual growth rate applied to the monthly rule.
    """

    model_config = ConfigDict(extra="forbid")

    start_year: int = Field(..., ge=0)
    end_year: int = Field(..., ge=0)
    amount: float = Field(..., ge=0.0)
    frequency: str = Field("monthly")
    growth: float = Field(0.0, ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def _check_span(self) -> ContributionEventConfig:
        """Validate the temporal span and supported frequencies."""

        if self.end_year < self.start_year:
            msg = "contribution_plan entries require end_year >= start_year"
            raise ValueError(msg)
        if self.frequency not in {"monthly", "lump_sum"}:
            msg = "contribution_plan frequency must be 'monthly' or 'lump_sum'"
            raise ValueError(msg)
        return self


class WithdrawalEventConfig(BaseModel):
    """Single withdrawal scheduled at a specific relative year."""

    model_config = ConfigDict(extra="forbid")

    year: int = Field(..., ge=0)
    amount: float = Field(..., gt=0.0)


class HouseholdConfig(BaseModel):
    """Schema for household specific information feeding goal planning.

    Attributes:
      investor: Identifier used to label reports and artefacts.
      age: Current age of the investor in years.
      contrib_monthly: Expected baseline monthly contribution amount in euros.
      horizon_years: Investment horizon expressed in years.
      cvar_cap_1m: Maximum acceptable one-month CVaR expressed as a fraction.
      edar_cap_3y: Maximum acceptable three-year Expected Drawdown at Risk fraction.
      initial_wealth: Optional current investable wealth.
      contribution_growth: Annual growth rate applied to the baseline contribution.
      contribution_plan: Optional list of overrides for cash-flow planning.
      withdrawals: Optional list of scheduled withdrawals.
    """

    model_config = ConfigDict(extra="forbid")

    investor: str = Field("household", min_length=1, max_length=64)
    age: int = Field(..., ge=18, le=100)
    contrib_monthly: float = Field(..., ge=0.0)
    horizon_years: int = Field(..., ge=1)
    cvar_cap_1m: float = Field(..., ge=0.0, le=1.0)
    edar_cap_3y: float = Field(..., ge=0.0, le=1.0)
    initial_wealth: float = Field(0.0, ge=0.0)
    contribution_growth: float = Field(0.02, ge=-1.0, le=1.0)
    contribution_plan: list[ContributionEventConfig] = Field(default_factory=list)
    withdrawals: list[WithdrawalEventConfig] = Field(default_factory=list)


class ParamsConfig(BaseModel):
    """Top-level configuration for parameter thresholds and policies.

    Attributes:
      currency_base: ISO currency code used as reporting base.
      household: Nested household parameters.
      filters: Filter settings controlling the investable universe.
      rebalancing: Tactical rebalancing configuration.
    """

    model_config = ConfigDict(extra="forbid")

    currency_base: str = Field(..., min_length=3, max_length=3)
    household: HouseholdConfig
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    rebalancing: RebalancingConfig


class TauThresholds(BaseModel):
    """Tolerance thresholds controlling statistical stability checks.

    Attributes:
      IR_view: Minimum information ratio for Black-Litterman overrides.
      sigma_rel: Maximum allowed relative deviation for the covariance matrix.
      delta_rho: Maximum absolute variation allowed for correlations.
      beta_CI_width: Maximum width for the 80%% beta confidence interval before capping.
      rc_tol: Allowed deviation from equal risk contributions.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ir_view: float = Field(..., ge=0.0, le=1.0, alias="IR_view")
    sigma_rel: float = Field(..., ge=0.0, le=1.0, alias="sigma_rel")
    delta_rho: float = Field(..., ge=0.0, le=1.0, alias="delta_rho")
    beta_ci_width: float = Field(..., ge=0.0, le=1.0, alias="beta_CI_width")
    rc_tol: float = Field(..., ge=0.0, le=1.0, alias="rc_tol")


class ExecutionThresholds(BaseModel):
    """Constraints applied during execution and tax-aware sizing.

    Attributes:
      turnover_cap: Maximum portfolio turnover allowed per rebalance.
      gross_leverage_cap: Maximum gross leverage allowed.
      TE_max_factor: Tracking error cap applied to each factor sleeve.
      adv_cap_ratio: Fraction of average daily volume eligible for trading.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    turnover_cap: float = Field(..., ge=0.0, le=1.0, alias="turnover_cap")
    gross_leverage_cap: float = Field(..., ge=1.0, le=5.0, alias="gross_leverage_cap")
    te_max_factor: float = Field(..., ge=0.0, le=0.5, alias="TE_max_factor")
    adv_cap_ratio: float = Field(..., ge=0.0, le=1.0, alias="adv_cap_ratio")


class RegimeCommitteeWeights(BaseModel):
    """Weights assigned to the three regime committee components."""

    model_config = ConfigDict(extra="forbid")

    hmm: float = Field(0.5, ge=0.0)
    volatility: float = Field(0.3, ge=0.0)
    macro: float = Field(0.2, ge=0.0)

    @model_validator(mode="after")
    def _check_sum(self) -> RegimeCommitteeWeights:
        """Ensure at least one component is active."""

        total = float(self.hmm + self.volatility + self.macro)
        if total <= 0.0:
            msg = "regime.weights must allocate positive mass"
            raise ValueError(msg)
        return self


class RegimeVolatilityConfig(BaseModel):
    """Configuration controlling the volatility HSMM post-processing."""

    model_config = ConfigDict(extra="forbid")

    window: int = Field(63, ge=5, le=252)
    min_duration: int = Field(5, ge=1, le=63)
    smoothing: int = Field(5, ge=1, le=63)


class RegimeMacroConfig(BaseModel):
    """Configuration parameters for macro slowdown triggers."""

    model_config = ConfigDict(extra="forbid")

    inflation_weight: float = Field(0.4, ge=0.0)
    pmi_weight: float = Field(0.35, ge=0.0)
    real_rate_weight: float = Field(0.25, ge=0.0)
    pmi_threshold: float = Field(50.0)
    real_rate_threshold: float = Field(0.0)
    smoothing: int = Field(3, ge=1, le=12)

    @model_validator(mode="after")
    def _check_weights(self) -> RegimeMacroConfig:
        """The macro trigger requires at least one active component."""

        weight_sum = float(self.inflation_weight + self.pmi_weight + self.real_rate_weight)
        if weight_sum <= 0.0:
            msg = "regime.macro weights must sum to a positive value"
            raise ValueError(msg)
        return self


class RegimeThresholds(BaseModel):
    """Parameters governing the regime engine and hysteresis filters.

    Attributes:
      on: Probability threshold triggering the crisis regime.
      off: Probability threshold to exit the crisis regime.
      dwell_days: Minimum days to remain in the active regime before evaluation.
      cooldown_days: Cool-down window before another activation.
      activate_streak: Minimum consecutive observations above ``on`` before activation.
      deactivate_streak: Minimum consecutive observations below ``off`` before deactivation.
      weights: Committee weights applied to the HMM, volatility and macro scores.
      volatility: Volatility model parameters for HSMM smoothing.
      macro: Macro trigger configuration for inflation, PMI and real rates.
    """

    model_config = ConfigDict(extra="forbid")

    on: float = Field(..., ge=0.0, le=1.0)
    off: float = Field(..., ge=0.0, le=1.0)
    dwell_days: int = Field(..., ge=1, le=252)
    cooldown_days: int = Field(..., ge=0, le=252)
    activate_streak: int = Field(3, ge=1, le=10)
    deactivate_streak: int = Field(3, ge=1, le=10)
    weights: RegimeCommitteeWeights = Field(default_factory=RegimeCommitteeWeights)
    volatility: RegimeVolatilityConfig = Field(default_factory=RegimeVolatilityConfig)
    macro: RegimeMacroConfig = Field(default_factory=RegimeMacroConfig)

    @model_validator(mode="after")
    def _check_hysteresis(self) -> RegimeThresholds:
        """Ensure that activation and deactivation probabilities are coherent."""

        if self.on <= self.off:
            msg = "regime.on must be greater than regime.off to avoid flip-flops"
            raise ValueError(msg)
        return self


class DriftThresholds(BaseModel):
    """Tolerance band thresholds for drift-based decision gates.

    Attributes:
      weight_tol: Allowed deviation in absolute weight terms before trading.
      rc_tol: Allowed deviation in risk contribution before trading.
    """

    model_config = ConfigDict(extra="forbid")

    weight_tol: float = Field(..., ge=0.0, le=0.5)
    rc_tol: float = Field(..., ge=0.0, le=0.5)


class ThresholdsConfig(BaseModel):
    """Aggregate structure containing every execution and monitoring threshold.

    Attributes:
      vol_target_annual: Annualised volatility target for portfolio construction.
      tau: Stability tolerances for ensemble estimates.
      execution: Execution gating limits.
      regime: Regime engine hysteresis configuration.
      drift: Drift-based no-trade bands.
    """

    model_config = ConfigDict(extra="forbid")

    vol_target_annual: float = Field(..., ge=0.01, le=0.5)
    tau: TauThresholds
    execution: ExecutionThresholds
    regime: RegimeThresholds
    drift: DriftThresholds


class GoalEntry(BaseModel):
    """Single household goal describing target wealth and probability target.

    Attributes:
      name: Human readable goal identifier.
      W: Target wealth level in euros.
      T_years: Investment horizon for the goal in years.
      p_min: Minimum acceptable probability of success.
      weight: Goal weight for aggregate scoring.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    W: float = Field(..., gt=0.0)
    T_years: int = Field(..., ge=1)
    p_min: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)


class GoalsConfig(BaseModel):
    """Collection of household goals with aggregate diagnostics.

    Attributes:
      goals: Non-empty list of :class:`GoalEntry` items describing each target.
    """

    model_config = ConfigDict(extra="forbid")

    goals: list[GoalEntry]

    @model_validator(mode="after")
    def _check_non_empty(self) -> GoalsConfig:
        """Ensure that at least one goal is configured."""

        if not self.goals:
            msg = "goals list cannot be empty"
            raise ValueError(msg)
        return self


def _validate_file(
    label: str,
    path: Path,
    model: type[BaseModel],
    summary: ValidationSummary,
) -> None:
    """Load ``path`` and validate its payload against ``model``.

    Args:
      label: Human readable identifier used in diagnostics.
      path: Filesystem path pointing to the YAML document.
      model: Pydantic model used for schema validation.
      summary: Mutable :class:`ValidationSummary` collecting diagnostics.
    """

    if not path.exists():
        summary.errors.append(f"{label}: missing file at {path}")
        return

    payload = read_yaml(path)
    if payload is None:
        summary.errors.append(f"{label}: file at {path} is empty")
        return

    try:
        parsed = model.model_validate(payload)
    except ValidationError as exc:
        for issue in exc.errors():
            location = ".".join(str(piece) for piece in issue.get("loc", ())) or label
            message = issue.get("msg", "invalid value")
            summary.errors.append(f"{label}.{location}: {message}")
        return

    summary.configs[label] = parsed.model_dump(by_alias=True)


def validate_configs(
    *,
    params_path: Path | str = Path("configs") / "params.yml",
    thresholds_path: Path | str = Path("configs") / "thresholds.yml",
    goals_path: Path | str = Path("configs") / "goals.yml",
) -> ValidationSummary:
    """Validate FAIR-III YAML configuration files and return diagnostics.

    Args:
      params_path: Path to the household parameter YAML.
      thresholds_path: Path to the thresholds configuration YAML.
      goals_path: Path to the goals YAML.

    Returns:
      Validation summary containing collected errors, warnings and parsed payloads.
    """

    summary = ValidationSummary()
    _validate_file("params", Path(params_path), ParamsConfig, summary)
    _validate_file("thresholds", Path(thresholds_path), ThresholdsConfig, summary)
    _validate_file("goals", Path(goals_path), GoalsConfig, summary)

    goals_payload = summary.configs.get("goals", {}).get("goals", [])
    if goals_payload:
        total_weight = sum(item["weight"] for item in goals_payload)
        if abs(total_weight - 1.0) > 0.05:
            summary.warnings.append(
                f"goals.weights: sum is {total_weight:.3f}; consider normalising to 1.0"
            )

    thresholds_payload = summary.configs.get("thresholds", {})
    if thresholds_payload:
        drift_tol = thresholds_payload.get("drift", {})
        weight_tol = drift_tol.get("weight_tol")
        rc_tol = drift_tol.get("rc_tol")
        if weight_tol is not None and rc_tol is not None and weight_tol < rc_tol / 2:
            summary.warnings.append(
                "drift: weight tolerance is much tighter than risk contribution tolerance"
            )
        regime_payload = thresholds_payload.get("regime", {})
        weights_payload = regime_payload.get("weights", {})
        weight_components = [
            float(weights_payload.get(key, 0.0)) for key in ("hmm", "volatility", "macro")
        ]
        weight_sum = sum(weight_components)
        if weight_sum > 0 and abs(weight_sum - 1.0) > 0.25:
            summary.warnings.append(
                f"regime.weights: sum is {weight_sum:.3f}; consider normalising to 1.0"
            )
        macro_payload = regime_payload.get("macro", {})
        macro_sum = sum(
            float(macro_payload.get(key, 0.0))
            for key in ("inflation_weight", "pmi_weight", "real_rate_weight")
        )
        if macro_sum <= 0.0:
            summary.warnings.append("regime.macro: at least one macro weight must be positive")

    return summary
