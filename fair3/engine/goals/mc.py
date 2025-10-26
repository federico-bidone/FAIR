"""Monte Carlo goal simulation utilities.

This module implements a deterministic Monte Carlo engine used to evaluate
household goals under different regime assumptions. The simulator models
cash-flow plans with contributions and withdrawals, applies glidepath
adjustments based on the probability of success, and produces artefacts for
the CLI interface.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from fair3.engine.utils.io import ensure_dir, read_yaml, safe_path_segment

__all__ = [
    "GoalConfig",
    "GoalParameters",
    "ContributionRule",
    "WithdrawalRule",
    "GoalSimulationSummary",
    "GoalArtifacts",
    "load_goal_configs",
    "generate_regime_curves",
    "regime_curves_from_panel",
    "build_contribution_schedule",
    "build_withdrawal_schedule",
    "build_cashflow_schedule",
    "build_glidepath",
    "simulate_goals",
    "goal_monte_carlo",
    "write_goal_artifacts",
    "run_goal_monte_carlo",
    "load_goal_configs_from_yaml",
    "load_goal_parameters",
]


@dataclass(frozen=True)
class GoalConfig:
    """Configuration describing a household goal.

    Attributes:
      name: Identifier used in reports and charts.
      target: Wealth target expressed in euros.
      horizon_years: Investment horizon in years.
      p_min: Minimum acceptable probability of success.
      weight: Weight used to aggregate probabilities across goals.
    """

    name: str
    target: float
    horizon_years: int
    p_min: float
    weight: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> GoalConfig:
        """Create a :class:`GoalConfig` from a mapping.

        Args:
          payload: Mapping extracted from YAML or JSON configuration files.

        Returns:
          A populated :class:`GoalConfig` instance.
        """

        return cls(
            name=str(payload["name"]),
            target=float(payload["W"]),
            horizon_years=int(payload["T_years"]),
            p_min=float(payload["p_min"]),
            weight=float(payload.get("weight", 1.0)),
        )


@dataclass(frozen=True)
class ContributionRule:
    """Monthly or lump-sum contribution adjustment.

    Attributes:
      start_month: First month (inclusive) where the rule applies.
      end_month: Last month (exclusive) reached by the rule.
      amount: Contribution amount in euros (monthly or lump-sum per year).
      frequency: Either ``"monthly"`` or ``"lump_sum"``.
      growth: Annual growth rate applied to the rule.
    """

    start_month: int
    end_month: int
    amount: float
    frequency: str
    growth: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ContributionRule:
        """Build a rule from a YAML mapping while validating fields.

        Args:
          payload: Mapping containing ``start_year``, ``end_year`` and ``amount``
            keys alongside optional ``frequency`` and ``growth``.

        Returns:
          A :class:`ContributionRule` covering the requested horizon.
        """

        start_year = int(payload.get("start_year", 0))
        end_year = int(payload.get("end_year", start_year))
        amount = float(payload.get("amount", 0.0))
        frequency = str(payload.get("frequency", "monthly"))
        growth = float(payload.get("growth", 0.0))
        start_month = max(0, start_year * 12)
        end_month = max(start_month, (end_year + 1) * 12)
        return cls(
            start_month=start_month,
            end_month=end_month,
            amount=amount,
            frequency=frequency,
            growth=growth,
        )


@dataclass(frozen=True)
class WithdrawalRule:
    """Withdrawal event expressed in months from the current date.

    Attributes:
      month: Month index when the withdrawal is executed.
      amount: Withdrawal amount expressed in euros.
    """

    month: int
    amount: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> WithdrawalRule:
        """Construct a withdrawal rule from a mapping.

        Args:
          payload: Mapping with ``year`` and ``amount`` entries.

        Returns:
          A :class:`WithdrawalRule` with the requested timing.
        """

        year = int(payload.get("year", 0))
        month = max(0, year * 12)
        amount = float(payload.get("amount", 0.0))
        return cls(month=month, amount=amount)


@dataclass(frozen=True)
class GoalParameters:
    """Household parameters required by the goal simulator.

    Attributes:
      investor: Identifier used in reports and filenames.
      monthly_contribution: Baseline monthly contribution amount in euros.
      contribution_growth: Annual growth applied to baseline contributions.
      initial_wealth: Starting investable wealth in euros.
      contribution_plan: Optional recurring contribution adjustments.
      withdrawals: Optional scheduled withdrawals.
    """

    investor: str
    monthly_contribution: float
    contribution_growth: float
    initial_wealth: float
    contribution_plan: tuple[ContributionRule, ...]
    withdrawals: tuple[WithdrawalRule, ...]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> GoalParameters:
        """Instantiate parameters from a mapping payload.

        Args:
          payload: Mapping containing ``investor`` and household cash-flow
            configuration.

        Returns:
          A :class:`GoalParameters` instance with normalised rules.
        """

        investor = str(payload.get("investor", "household"))
        monthly_contribution = float(payload.get("contrib_monthly", 0.0))
        contribution_growth = float(payload.get("contribution_growth", 0.02))
        initial_wealth = float(payload.get("initial_wealth", 0.0))
        raw_contribs = payload.get("contribution_plan", [])
        contribution_plan = tuple(
            ContributionRule.from_mapping(item)
            for item in raw_contribs
            if isinstance(item, Mapping)
        )
        raw_withdrawals = payload.get("withdrawals", [])
        withdrawals = tuple(
            WithdrawalRule.from_mapping(item)
            for item in raw_withdrawals
            if isinstance(item, Mapping)
        )
        return cls(
            investor=investor,
            monthly_contribution=monthly_contribution,
            contribution_growth=contribution_growth,
            initial_wealth=initial_wealth,
            contribution_plan=contribution_plan,
            withdrawals=withdrawals,
        )


@dataclass(frozen=True)
class RegimeCurves:
    """Synthetic regime curves for Monte Carlo simulation.

    Attributes:
      base_mu: Expected returns for the base regime per month.
      base_sigma: Volatility for the base regime per month.
      crisis_mu: Expected returns during crisis periods per month.
      crisis_sigma: Volatility during crisis periods per month.
      crisis_probability: Probability of being in crisis each month.
    """

    base_mu: np.ndarray
    base_sigma: np.ndarray
    crisis_mu: np.ndarray
    crisis_sigma: np.ndarray
    crisis_probability: np.ndarray

    def slice(self, periods: int) -> RegimeCurves:
        """Return the first ``periods`` observations for each curve.

        Args:
          periods: Number of monthly observations to retain.

        Returns:
          A :class:`RegimeCurves` truncated to the requested horizon.
        """

        return RegimeCurves(
            base_mu=self.base_mu[:periods],
            base_sigma=self.base_sigma[:periods],
            crisis_mu=self.crisis_mu[:periods],
            crisis_sigma=self.crisis_sigma[:periods],
            crisis_probability=self.crisis_probability[:periods],
        )


@dataclass(frozen=True)
class GoalSimulationSummary:
    """Aggregate simulation outputs for a set of household goals.

    Attributes:
      results: DataFrame with per-goal summary statistics.
      weighted_probability: Weighted probability of success across goals.
      draws: Number of Monte Carlo draws executed.
      seed: Random seed used to initialise the RNG chain.
      glidepaths: Mapping goal name -> glidepath DataFrame.
      fan_charts: Mapping goal name -> fan-chart DataFrame.
    """

    results: pd.DataFrame
    weighted_probability: float
    draws: int
    seed: int
    glidepaths: dict[str, pd.DataFrame]
    fan_charts: dict[str, pd.DataFrame]


@dataclass(frozen=True)
class GoalArtifacts:
    """Paths to the generated goal artefacts.

    Attributes:
      summary_csv: CSV file containing per-goal statistics.
      glidepath_csv: CSV aggregating glidepath allocations.
      fan_chart_csv: CSV storing monthly fan-chart percentiles.
      report_pdf: PDF file with probability bars and glidepath plots.
    """

    summary_csv: Path
    glidepath_csv: Path
    fan_chart_csv: Path
    report_pdf: Path


def load_goal_configs(payload: Sequence[Mapping[str, object]] | None) -> list[GoalConfig]:
    """Parse a list of goal configuration mappings.

    Args:
      payload: Iterable of dictionaries describing each goal.

    Returns:
      A list of :class:`GoalConfig` instances.
    """

    if not payload:
        return []
    return [GoalConfig.from_mapping(item) for item in payload]


def generate_regime_curves(periods: int, seed: int) -> RegimeCurves:
    """Generate synthetic regime parameters for Monte Carlo sampling.

    Args:
      periods: Number of months to generate.
      seed: Random seed controlling the RNG.

    Returns:
      A :class:`RegimeCurves` instance with synthetic parameters.
    """

    rng = np.random.default_rng(seed)
    base_mu = rng.normal(0.004, 0.0015, size=periods)
    base_sigma = rng.uniform(0.01, 0.03, size=periods)
    crisis_mu = rng.normal(-0.02, 0.008, size=periods)
    crisis_sigma = rng.uniform(0.04, 0.08, size=periods)
    crisis_probability = np.clip(rng.normal(0.15, 0.05, size=periods), 0.02, 0.45)
    return RegimeCurves(
        base_mu=base_mu,
        base_sigma=base_sigma,
        crisis_mu=crisis_mu,
        crisis_sigma=crisis_sigma,
        crisis_probability=crisis_probability,
    )


def regime_curves_from_panel(panel: pd.DataFrame, periods: int) -> RegimeCurves:
    """Create regime curves from a calibrated panel.

    Args:
      panel: DataFrame with columns ``mu_base``, ``sigma_base``, ``mu_crisis``,
        ``sigma_crisis`` and ``p_crisis``.
      periods: Number of periods requested by the simulator.

    Returns:
      A :class:`RegimeCurves` derived from the supplied panel.

    Raises:
      ValueError: If required columns are missing or the panel is empty.
    """

    required = {"mu_base", "sigma_base", "mu_crisis", "sigma_crisis", "p_crisis"}
    missing = required - set(panel.columns)
    if missing:
        raise ValueError(f"regime panel missing columns: {sorted(missing)}")
    if panel.empty:
        raise ValueError("regime panel must contain at least one row")

    trimmed = panel.loc[:, sorted(required)].copy()
    if periods <= 0:
        zero = np.zeros(0, dtype="float64")
        return RegimeCurves(zero, zero, zero, zero, zero)

    trimmed = trimmed.iloc[:periods].reset_index(drop=True)
    if len(trimmed) < periods:
        last_row = trimmed.iloc[-1:]
        repeats = pd.concat([last_row] * (periods - len(trimmed)), ignore_index=True)
        trimmed = pd.concat([trimmed, repeats], ignore_index=True)

    base_mu = trimmed["mu_base"].to_numpy(dtype="float64")
    base_sigma = np.clip(trimmed["sigma_base"].to_numpy(dtype="float64"), 1e-6, None)
    crisis_mu = trimmed["mu_crisis"].to_numpy(dtype="float64")
    crisis_sigma = np.clip(trimmed["sigma_crisis"].to_numpy(dtype="float64"), 1e-6, None)
    crisis_probability = np.clip(trimmed["p_crisis"].to_numpy(dtype="float64"), 0.0, 1.0)
    return RegimeCurves(base_mu, base_sigma, crisis_mu, crisis_sigma, crisis_probability)


def build_contribution_schedule(
    periods: int,
    monthly_contribution: float,
    growth_rate: float = 0.02,
    rules: Sequence[ContributionRule] | None = None,
) -> np.ndarray:
    """Return the deterministic contribution schedule over ``periods`` months.

    Args:
      periods: Number of months to generate.
      monthly_contribution: Baseline monthly contribution in euros.
      growth_rate: Annual growth rate applied to the baseline.
      rules: Optional recurring contribution rules that override the baseline.

    Returns:
      Array containing net contributions for each month.
    """

    if periods <= 0:
        return np.zeros(0, dtype="float64")

    timeline = np.arange(periods, dtype="float64")
    monthly_growth = (1.0 + growth_rate) ** (1.0 / 12.0) - 1.0
    schedule = np.full(periods, float(monthly_contribution), dtype="float64")
    schedule *= (1.0 + monthly_growth) ** timeline

    if not rules:
        return schedule

    for rule in rules:
        start = min(periods, max(0, rule.start_month))
        end = min(periods, max(rule.end_month, start + 1))
        if start >= periods:
            continue
        if rule.frequency == "monthly":
            months = np.arange(start, end, dtype=int)
            rule_growth = (1.0 + rule.growth) ** (1.0 / 12.0) - 1.0
            increments = rule.amount * (1.0 + rule_growth) ** np.arange(len(months))
            schedule[months] += increments
        elif rule.frequency == "lump_sum":
            yearly_growth = 1.0 + rule.growth
            amount = rule.amount
            for month in range(rule.start_month, rule.end_month, 12):
                if month >= periods:
                    break
                schedule[month] += amount
                amount *= yearly_growth
        else:  # pragma: no cover - guarded by schema validation
            msg = f"Unsupported contribution frequency: {rule.frequency}"
            raise ValueError(msg)
    return schedule


def build_withdrawal_schedule(
    periods: int, withdrawals: Sequence[WithdrawalRule] | None
) -> np.ndarray:
    """Return the withdrawal schedule as negative cash flows.

    Args:
      periods: Number of months to generate.
      withdrawals: Optional withdrawal rules.

    Returns:
      Array of withdrawals (negative amounts) for each month.
    """

    if periods <= 0:
        return np.zeros(0, dtype="float64")

    schedule = np.zeros(periods, dtype="float64")
    if not withdrawals:
        return schedule

    for rule in withdrawals:
        month = max(0, rule.month)
        if month >= periods:
            continue
        schedule[month] -= rule.amount
    return schedule


def build_cashflow_schedule(periods: int, parameters: GoalParameters) -> np.ndarray:
    """Combine contributions and withdrawals into a single schedule.

    Args:
      periods: Number of months to generate.
      parameters: Household parameters controlling contributions and withdrawals.

    Returns:
      Array of net cash flows to apply at each month.
    """

    contributions = build_contribution_schedule(
        periods,
        parameters.monthly_contribution,
        parameters.contribution_growth,
        parameters.contribution_plan,
    )
    withdrawals = build_withdrawal_schedule(periods, parameters.withdrawals)
    return contributions + withdrawals


def build_glidepath(
    horizon_years: int,
    start_risk: float = 0.75,
    end_risk: float = 0.30,
) -> pd.DataFrame:
    """Construct a linear glidepath between growth and defensive assets.

    Args:
      horizon_years: Investment horizon in years.
      start_risk: Initial allocation to growth assets.
      end_risk: Final allocation to growth assets.

    Returns:
      DataFrame indexed by year with growth, defensive and TE scale columns.
    """

    years = np.arange(max(0, horizon_years) + 1)
    growth = np.linspace(start_risk, end_risk, len(years))
    growth = np.clip(growth, 0.0, 1.0)
    defensive = 1.0 - growth
    te_scale = np.ones_like(growth, dtype="float64")
    return pd.DataFrame(
        {"growth": growth, "defensive": defensive, "te_budget_scale": te_scale},
        index=years,
    )


def _adjust_glidepath(
    glidepath: pd.DataFrame,
    probability: float,
    threshold: float,
    expected_wealth: float,
    initial_wealth: float,
) -> pd.DataFrame:
    """Adjust the glidepath according to the probability of success.

    Args:
      glidepath: Baseline glidepath DataFrame.
      probability: Probability of reaching the goal target.
      threshold: Minimum acceptable probability.
      expected_wealth: Expected terminal wealth across the simulations.
      initial_wealth: Starting investable wealth before contributions.

    Returns:
      Adjusted glidepath with updated TE budget scale.
    """

    delta = probability - threshold
    adjustment = 0.0
    te_scale = 1.0
    wealth_ratio = expected_wealth / max(initial_wealth, 1e-9)
    if wealth_ratio < 1.0:
        adjustment = 0.05
        te_scale = 1.10
    elif delta >= 0.05:
        adjustment = -0.10
        te_scale = 0.85
    elif delta <= -0.05:
        adjustment = 0.05
        te_scale = 1.10

    adjusted = glidepath.copy()
    adjusted["growth"] = np.clip(adjusted["growth"] + adjustment, 0.0, 1.0)
    adjusted["defensive"] = 1.0 - adjusted["growth"]
    adjusted["te_budget_scale"] = np.clip(te_scale, 0.5, 1.2)
    return adjusted


def _sample_returns(curves: RegimeCurves, rng: np.random.Generator, draws: int) -> np.ndarray:
    """Sample monthly returns using Bernoulli regime switches.

    Args:
      curves: Regime curves describing base and crisis behaviour.
      rng: Random number generator.
      draws: Number of Monte Carlo paths to sample.

    Returns:
      Array with shape ``(draws, periods)`` containing simulated returns.
    """

    periods = curves.base_mu.size
    if periods == 0:
        return np.zeros((draws, 0), dtype="float64")
    crisis_mask = rng.random((draws, periods)) < curves.crisis_probability[None, :]
    mu = np.where(crisis_mask, curves.crisis_mu[None, :], curves.base_mu[None, :])
    sigma = np.where(crisis_mask, curves.crisis_sigma[None, :], curves.base_sigma[None, :])
    sigma = np.clip(sigma, 1e-6, None)
    return rng.normal(mu, sigma)


def _simulate_goal(
    goal: GoalConfig,
    curves: RegimeCurves,
    rng: np.random.Generator,
    draws: int,
    parameters: GoalParameters,
) -> tuple[dict[str, float | str | bool], pd.DataFrame, pd.DataFrame]:
    """Simulate the final wealth distribution for a single goal.

    Args:
      goal: Goal configuration describing the target and horizon.
      curves: Regime curves used to sample returns.
      rng: Random number generator initialised for this goal.
      draws: Number of Monte Carlo paths to simulate.
      parameters: Household parameters controlling cash flows.

    Returns:
      A tuple containing the summary dictionary, adjusted glidepath and
      fan-chart DataFrame for the goal.
    """

    periods = goal.horizon_years * 12
    sliced = curves.slice(periods)
    returns = _sample_returns(sliced, rng, draws)
    schedule = build_cashflow_schedule(periods, parameters)

    wealth = np.full(draws, float(parameters.initial_wealth), dtype="float64")
    if periods > 0:
        wealth_paths = np.empty((draws, periods), dtype="float64")
        for idx in range(periods):
            wealth += schedule[idx]
            wealth *= 1.0 + returns[:, idx]
            wealth_paths[:, idx] = wealth
        final_wealth = wealth_paths[:, -1]
        quantiles_path = np.quantile(wealth_paths, [0.05, 0.50, 0.95], axis=0)
        fan_chart = pd.DataFrame(
            {
                "p5": quantiles_path[0],
                "p50": quantiles_path[1],
                "p95": quantiles_path[2],
            },
            index=pd.RangeIndex(periods, name="month"),
        )
    else:
        final_wealth = wealth
        fan_chart = pd.DataFrame(columns=["p5", "p50", "p95"], index=pd.RangeIndex(0, name="month"))

    probability = float(np.mean(final_wealth >= goal.target))
    quantiles = np.quantile(final_wealth, [0.05, 0.50, 0.95]) if final_wealth.size else np.zeros(3)
    expected = (
        float(np.mean(final_wealth)) if final_wealth.size else float(parameters.initial_wealth)
    )
    base_glidepath = build_glidepath(goal.horizon_years)
    glidepath = _adjust_glidepath(
        base_glidepath,
        probability,
        goal.p_min,
        expected,
        float(parameters.initial_wealth),
    )

    result = {
        "goal": goal.name,
        "probability": probability,
        "target": goal.target,
        "p_min": goal.p_min,
        "expected_wealth": expected,
        "p5": float(quantiles[0]),
        "p50": float(quantiles[1]),
        "p95": float(quantiles[2]),
        "passes": probability >= goal.p_min,
        "weight": goal.weight,
        "te_scale": float(glidepath["te_budget_scale"].iloc[-1]),
    }
    return result, glidepath, fan_chart


def simulate_goals(
    goals: Sequence[GoalConfig],
    *,
    draws: int,
    seed: int,
    parameters: GoalParameters,
    assumptions: RegimeCurves | None = None,
    regime_panel: pd.DataFrame | None = None,
) -> GoalSimulationSummary:
    """Run the Monte Carlo simulator returning summary statistics.

    Args:
      goals: Collection of goals to simulate.
      draws: Number of Monte Carlo paths.
      seed: Random seed used to initialise the RNG chain.
      parameters: Household parameters driving cash flows.
      assumptions: Optional precomputed regime curves.
      regime_panel: Optional panel used to derive regime curves.

    Returns:
      A :class:`GoalSimulationSummary` with per-goal results and diagnostics.
    """

    if not goals:
        empty = pd.DataFrame(
            columns=[
                "goal",
                "probability",
                "target",
                "p_min",
                "expected_wealth",
                "p5",
                "p50",
                "p95",
                "passes",
                "weight",
                "te_scale",
            ]
        )
        return GoalSimulationSummary(
            results=empty,
            weighted_probability=float("nan"),
            draws=draws,
            seed=seed,
            glidepaths={},
            fan_charts={},
        )

    max_horizon_years = max(goal.horizon_years for goal in goals)
    max_periods = max_horizon_years * 12
    if assumptions is not None:
        curves = assumptions
    elif regime_panel is not None:
        curves = regime_curves_from_panel(regime_panel, max_periods)
    else:
        curves = generate_regime_curves(max_periods, seed)

    seed_sequence = np.random.SeedSequence(seed)
    child_sequences = seed_sequence.spawn(len(goals))

    results: list[dict[str, float | str | bool]] = []
    glidepaths: dict[str, pd.DataFrame] = {}
    fan_charts: dict[str, pd.DataFrame] = {}
    for goal, child in zip(goals, child_sequences, strict=False):
        goal_rng = np.random.default_rng(child)
        summary, glidepath, fan_chart = _simulate_goal(goal, curves, goal_rng, draws, parameters)
        results.append(summary)
        glidepaths[goal.name] = glidepath
        fan_charts[goal.name] = fan_chart

    frame = pd.DataFrame(results)
    weights = frame["weight"].to_numpy(dtype="float64")
    probabilities = frame["probability"].to_numpy(dtype="float64")
    total_weight = float(np.sum(weights))
    if total_weight > 0.0:
        weighted_probability = float(np.average(probabilities, weights=weights))
    else:
        weighted_probability = float(np.mean(probabilities))

    return GoalSimulationSummary(
        results=frame,
        weighted_probability=weighted_probability,
        draws=draws,
        seed=seed,
        glidepaths=glidepaths,
        fan_charts=fan_charts,
    )


def _render_goal_pdf(summary: GoalSimulationSummary, investor: str, path: Path) -> Path:
    """Render a PDF visualising goal probabilities and glidepaths.

    Args:
      summary: Simulation summary returned by :func:`simulate_goals`.
      investor: Investor identifier used in the plot title.
      path: Destination PDF path.

    Returns:
      The ``path`` argument for convenience.
    """

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results = summary.results
    rows = max(1, len(results))
    fig, axes = plt.subplots(rows + 1, 1, figsize=(8, 3.5 * (rows + 1)))
    if not isinstance(axes, np.ndarray):  # pragma: no cover - mpl quirk
        axes = np.asarray([axes])

    if results.empty:
        axes[0].text(0.5, 0.5, "No goals configured", ha="center", va="center")
        axes[0].set_axis_off()
    else:
        for ax, row in zip(axes[:-1], results.itertuples(index=False), strict=False):
            fan_chart = summary.fan_charts.get(row.goal)
            if fan_chart is not None and not fan_chart.empty:
                months = fan_chart.index.to_numpy()
                ax.fill_between(
                    months,
                    fan_chart["p5"],
                    fan_chart["p95"],
                    color="#B9D6F2",
                    alpha=0.4,
                    label="5-95 pct",
                )
                ax.plot(months, fan_chart["p50"], color="#2E86AB", label="Median")
            ax.axhline(row.target, color="#D7263D", linestyle="--", linewidth=1.0, label="Target")
            ax.set_title(f"Goal: {row.goal} (p={row.probability:.2%}, threshold={row.p_min:.0%})")
            ax.set_xlabel("Month")
            ax.set_ylabel("Wealth (EUR)")
            ax.legend(loc="upper left")
            ax.text(
                0.02,
                0.95,
                f"Passes: {'yes' if row.passes else 'no'}\nTE scale: {row.te_scale:.2f}",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=9,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.6),
            )

    glide_ax = axes[-1]
    if summary.glidepaths:
        for name, frame in summary.glidepaths.items():
            years = frame.index.to_numpy()
            glide_ax.plot(years, frame["growth"], label=f"{name} growth")
            glide_ax.plot(years, frame["defensive"], linestyle="--", label=f"{name} defensive")
        glide_ax.set_xlabel("Years to horizon")
        glide_ax.set_ylabel("Allocation")
        glide_ax.set_ylim(0.0, 1.0)
        glide_ax.legend(loc="upper right", fontsize=9)
    else:
        glide_ax.set_axis_off()
    glide_ax.set_title("Glidepaths")

    fig.suptitle(
        f"Household Goals Monte Carlo — {investor} (draws={summary.draws}, seed={summary.seed})",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(path, format="pdf")
    plt.close(fig)
    return path


def _stacked_dataframe(frames: Mapping[str, pd.DataFrame], *, index_name: str) -> pd.DataFrame:
    """Stack goal-indexed DataFrames into a long-form representation.

    Args:
      frames: Mapping goal name -> DataFrame.
      index_name: Name assigned to the index column in the stacked frame.

    Returns:
      Concatenated DataFrame with ``goal`` and index columns.
    """

    if not frames:
        return pd.DataFrame(columns=["goal", index_name])
    stacked = []
    for name, frame in frames.items():
        exported = frame.copy()
        exported[index_name] = exported.index
        exported.insert(0, "goal", name)
        stacked.append(exported.reset_index(drop=True))
    return pd.concat(stacked, ignore_index=True)


def write_goal_artifacts(
    summary: GoalSimulationSummary,
    *,
    investor: str,
    output_dir: Path | None = None,
) -> GoalArtifacts:
    """Write CSV/PDF artefacts for the simulation.

    Args:
      summary: Result of :func:`simulate_goals`.
      investor: Investor identifier used in filenames.
      output_dir: Optional destination directory.

    Returns:
      Paths to the exported artefacts.
    """

    root = Path(output_dir) if output_dir is not None else Path("reports")
    root = root / "goals"
    ensure_dir(root)
    label = safe_path_segment(investor or "investor")

    summary_csv = root / f"goals_{label}_summary.csv"
    glidepath_csv = root / f"goals_{label}_glidepaths.csv"
    fan_chart_csv = root / f"goals_{label}_fan_chart.csv"
    report_pdf = root / f"goals_{label}.pdf"

    summary_export = summary.results.drop(columns=["weight"], errors="ignore")
    summary_export.to_csv(summary_csv, index=False)
    summary_export.to_csv(root / "summary.csv", index=False)
    glide_export = _stacked_dataframe(summary.glidepaths, index_name="year")
    glide_export.to_csv(glidepath_csv, index=False)
    fan_export = _stacked_dataframe(summary.fan_charts, index_name="month")
    fan_export.to_csv(fan_chart_csv, index=False)
    _render_goal_pdf(summary, investor, report_pdf)
    return GoalArtifacts(
        summary_csv=summary_csv,
        glidepath_csv=glidepath_csv,
        fan_chart_csv=fan_chart_csv,
        report_pdf=report_pdf,
    )


def goal_monte_carlo(
    parameters: GoalParameters,
    goals: Sequence[GoalConfig],
    *,
    draws: int,
    seed: int,
    regime_panel: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Execute the Monte Carlo engine returning a serialisable payload.

    Args:
      parameters: Household parameters controlling the simulation.
      goals: Sequence of household goals.
      draws: Number of Monte Carlo paths.
      seed: Random seed used to initialise the RNG chain.
      regime_panel: Optional regime panel used to calibrate the simulation.

    Returns:
      Dictionary containing summary statistics, glidepaths and fan-charts.
    """

    summary = simulate_goals(
        goals,
        draws=draws,
        seed=seed,
        parameters=parameters,
        regime_panel=regime_panel,
    )
    return {
        "results": summary.results.copy(),
        "glidepaths": {name: frame.copy() for name, frame in summary.glidepaths.items()},
        "fan_charts": {name: frame.copy() for name, frame in summary.fan_charts.items()},
        "weighted_probability": summary.weighted_probability,
        "seed": summary.seed,
        "draws": summary.draws,
    }


def run_goal_monte_carlo(
    goals: Sequence[GoalConfig],
    *,
    draws: int,
    seed: int,
    parameters: GoalParameters,
    output_dir: Path | None = None,
    regime_panel: pd.DataFrame | None = None,
) -> tuple[GoalSimulationSummary, GoalArtifacts]:
    """Run the full Monte Carlo workflow writing artefacts to disk.

    Args:
      goals: Sequence of goals to evaluate.
      draws: Number of Monte Carlo paths.
      seed: Random seed used to initialise the RNG chain.
      parameters: Household parameters controlling cash flows.
      output_dir: Optional directory for artefacts.
      regime_panel: Optional regime panel used for calibration.

    Returns:
      Tuple with the simulation summary and the exported artefacts.
    """

    summary = simulate_goals(
        goals,
        draws=draws,
        seed=seed,
        parameters=parameters,
        regime_panel=regime_panel,
    )
    artifacts = write_goal_artifacts(summary, investor=parameters.investor, output_dir=output_dir)
    return summary, artifacts


def load_goal_configs_from_yaml(path: Path | str) -> list[GoalConfig]:
    """Load goal configurations from a YAML file.

    Args:
      path: Path to the YAML document.

    Returns:
      List of :class:`GoalConfig` instances.
    """

    data = read_yaml(path)
    payload: Sequence[Mapping[str, object]] | None
    if isinstance(data, Mapping) and "goals" in data:
        payload = data["goals"]  # type: ignore[assignment]
    elif isinstance(data, Sequence):
        payload = data  # type: ignore[assignment]
    else:
        payload = None
    return load_goal_configs(payload)


def load_goal_parameters(path: Path | str) -> GoalParameters:
    """Helper to load household parameters used by the CLI.

    Args:
      path: Path to ``params.yml`` or similar configuration file.

    Returns:
      A :class:`GoalParameters` instance with default fallbacks.
    """

    data = read_yaml(path)
    if not isinstance(data, Mapping):
        return GoalParameters.from_mapping({})
    household = data.get("household", {})
    if not isinstance(household, Mapping):
        return GoalParameters.from_mapping({})
    return GoalParameters.from_mapping(household)
