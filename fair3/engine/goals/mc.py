"""Monte Carlo goal simulation utilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fair3.engine.utils.io import artifact_path, read_yaml

__all__ = [
    "GoalConfig",
    "GoalSimulationSummary",
    "GoalArtifacts",
    "load_goal_configs",
    "generate_regime_curves",
    "build_contribution_schedule",
    "build_glidepath",
    "simulate_goals",
    "write_goal_artifacts",
    "run_goal_monte_carlo",
    "load_goal_configs_from_yaml",
    "load_goal_parameters",
]


@dataclass(frozen=True)
class GoalConfig:
    """Configuration describing a household goal."""

    name: str
    target: float
    horizon_years: int
    p_min: float
    weight: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> GoalConfig:
        """Create a :class:`GoalConfig` from a mapping."""

        return cls(
            name=str(payload["name"]),
            target=float(payload["W"]),
            horizon_years=int(payload["T_years"]),
            p_min=float(payload["p_min"]),
            weight=float(payload.get("weight", 1.0)),
        )


@dataclass(frozen=True)
class RegimeCurves:
    """Synthetic regime curves for Monte Carlo simulation."""

    base_mu: np.ndarray
    base_sigma: np.ndarray
    crisis_mu: np.ndarray
    crisis_sigma: np.ndarray
    crisis_probability: np.ndarray

    def slice(self, periods: int) -> RegimeCurves:
        """Return the first ``periods`` observations for each curve."""

        return RegimeCurves(
            base_mu=self.base_mu[:periods],
            base_sigma=self.base_sigma[:periods],
            crisis_mu=self.crisis_mu[:periods],
            crisis_sigma=self.crisis_sigma[:periods],
            crisis_probability=self.crisis_probability[:periods],
        )


@dataclass(frozen=True)
class GoalSimulationSummary:
    """Aggregate simulation outputs for a set of household goals."""

    results: pd.DataFrame
    weighted_probability: float
    draws: int
    seed: int
    glidepath: pd.DataFrame


@dataclass(frozen=True)
class GoalArtifacts:
    """Paths to the generated goal artefacts."""

    summary_csv: Path
    glidepath_csv: Path
    report_pdf: Path


def load_goal_configs(payload: Sequence[Mapping[str, object]] | None) -> list[GoalConfig]:
    """Parse a list of goal configuration mappings."""

    if not payload:
        return []
    return [GoalConfig.from_mapping(item) for item in payload]


def generate_regime_curves(periods: int, seed: int) -> RegimeCurves:
    """Generate synthetic regime parameters for Monte Carlo sampling."""

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


def build_contribution_schedule(
    periods: int,
    monthly_contribution: float,
    growth_rate: float = 0.02,
) -> np.ndarray:
    """Return the deterministic contribution schedule over ``periods`` months."""

    if periods <= 0:
        return np.zeros(0, dtype="float64")
    monthly_growth = (1.0 + growth_rate) ** (1.0 / 12.0) - 1.0
    factors = (1.0 + monthly_growth) ** np.arange(periods)
    return np.asarray(monthly_contribution, dtype="float64") * factors


def build_glidepath(
    horizon_years: int,
    start_risk: float = 0.75,
    end_risk: float = 0.30,
) -> pd.DataFrame:
    """Construct a linear glidepath between growth and defensive assets."""

    years = np.arange(horizon_years + 1)
    growth = np.linspace(start_risk, end_risk, len(years))
    growth = np.clip(growth, 0.0, 1.0)
    defensive = 1.0 - growth
    return pd.DataFrame({"growth": growth, "defensive": defensive}, index=years)


def _sample_returns(
    curves: RegimeCurves,
    rng: np.random.Generator,
    draws: int,
) -> np.ndarray:
    """Sample monthly returns using Bernoulli regime switches."""

    periods = curves.base_mu.size
    if periods == 0:
        return np.zeros((draws, 0), dtype="float64")
    crisis_mask = rng.random((draws, periods)) < curves.crisis_probability[None, :]
    mu = np.where(crisis_mask, curves.crisis_mu[None, :], curves.base_mu[None, :])
    sigma = np.where(crisis_mask, curves.crisis_sigma[None, :], curves.base_sigma[None, :])
    return rng.normal(mu, sigma)


def _simulate_goal(
    goal: GoalConfig,
    curves: RegimeCurves,
    rng: np.random.Generator,
    draws: int,
    initial_wealth: float,
    monthly_contribution: float,
    contribution_growth: float,
) -> dict[str, float | str]:
    """Simulate final wealth distribution for a single goal."""

    periods = goal.horizon_years * 12
    sliced = curves.slice(periods)
    returns = _sample_returns(sliced, rng, draws)
    schedule = build_contribution_schedule(periods, monthly_contribution, contribution_growth)
    wealth = np.full(draws, float(initial_wealth), dtype="float64")
    for t in range(periods):
        wealth = (wealth + schedule[t]) * (1.0 + returns[:, t])
    probability = float(np.mean(wealth >= goal.target))
    quantiles = np.quantile(wealth, [0.05, 0.50, 0.95])
    expected = float(np.mean(wealth))
    return {
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
    }


def simulate_goals(
    goals: Sequence[GoalConfig],
    *,
    draws: int,
    seed: int,
    monthly_contribution: float,
    initial_wealth: float = 0.0,
    contribution_growth: float = 0.02,
    assumptions: RegimeCurves | None = None,
) -> GoalSimulationSummary:
    """Run the Monte Carlo simulator returning summary statistics."""

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
            ]
        )
        return GoalSimulationSummary(
            results=empty,
            weighted_probability=float("nan"),
            draws=draws,
            seed=seed,
            glidepath=pd.DataFrame(columns=["growth", "defensive"]),
        )

    max_horizon_years = max(goal.horizon_years for goal in goals)
    max_periods = max_horizon_years * 12
    curves = assumptions or generate_regime_curves(max_periods, seed)
    seed_sequence = np.random.SeedSequence(seed)
    child_sequences = seed_sequence.spawn(len(goals))

    results = []
    for goal, child in zip(goals, child_sequences, strict=False):
        goal_rng = np.random.default_rng(child)
        result = _simulate_goal(
            goal,
            curves,
            goal_rng,
            draws,
            initial_wealth,
            monthly_contribution,
            contribution_growth,
        )
        results.append(result)

    frame = pd.DataFrame(results)
    weights = frame["weight"].to_numpy(dtype="float64")
    probabilities = frame["probability"].to_numpy(dtype="float64")
    total_weight = float(np.sum(weights))
    if total_weight > 0.0:
        weighted_probability = float(np.average(probabilities, weights=weights))
    else:
        weighted_probability = float(np.mean(probabilities))

    glidepath = build_glidepath(max_horizon_years)
    return GoalSimulationSummary(
        results=frame,
        weighted_probability=weighted_probability,
        draws=draws,
        seed=seed,
        glidepath=glidepath,
    )


def _render_goal_pdf(summary: GoalSimulationSummary, path: Path) -> Path:
    """Render a compact PDF visualising goal probabilities and glidepath."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results = summary.results
    rows = max(1, len(results))
    fig, axes = plt.subplots(rows + 1, 1, figsize=(7, 3 * (rows + 1)))
    if not isinstance(axes, np.ndarray):  # pragma: no cover - mpl quirk
        axes = np.asarray([axes])

    for ax, (_, row) in zip(axes[:-1], results.iterrows(), strict=False):
        ax.bar([row["goal"]], [row["probability"]], color="#2E86AB")
        ax.axhline(row["p_min"], color="#D7263D", linestyle="--", linewidth=1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_ylabel("P(success)")
        ax.set_title(f"Goal: {row['goal']}")
        ax.text(
            0,
            row["probability"] + 0.02,
            f"p={row['probability']:.2%}\nTarget={row['target']:.0f}",
            ha="center",
            va="bottom",
        )

    glide_ax = axes[-1]
    if not summary.glidepath.empty:
        years = summary.glidepath.index.to_numpy()
        glide_ax.plot(years, summary.glidepath["growth"], label="Growth", color="#1B998B")
        glide_ax.plot(years, summary.glidepath["defensive"], label="Defensive", color="#C5D86D")
        glide_ax.set_xlabel("Years to retirement")
        glide_ax.set_ylabel("Allocation")
        glide_ax.set_ylim(0.0, 1.0)
        glide_ax.legend(loc="upper right")
    else:
        glide_ax.set_axis_off()
    glide_ax.set_title("Glidepath")

    fig.suptitle(
        f"Household Goals Monte Carlo (draws={summary.draws}, seed={summary.seed})",
        fontsize=12,
    )
    fig.tight_layout()
    fig.savefig(path, format="pdf")
    plt.close(fig)
    return path


def write_goal_artifacts(
    summary: GoalSimulationSummary,
    *,
    output_dir: Path | None = None,
) -> GoalArtifacts:
    """Write CSV/PDF artefacts for the simulation."""

    if output_dir is not None:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = artifact_path("goals", create=True).parent
    summary_csv = artifact_path("goals", "summary.csv", root=root)
    glidepath_csv = artifact_path("goals", "glidepath.csv", root=root)
    summary.results.drop(columns=["weight"]).to_csv(summary_csv, index=False)
    summary.glidepath.to_csv(glidepath_csv)
    report_pdf = artifact_path("goals", "report.pdf", root=root)
    _render_goal_pdf(summary, report_pdf)
    return GoalArtifacts(
        summary_csv=summary_csv,
        glidepath_csv=glidepath_csv,
        report_pdf=report_pdf,
    )


def run_goal_monte_carlo(
    goals: Sequence[GoalConfig],
    *,
    draws: int,
    seed: int,
    monthly_contribution: float,
    initial_wealth: float = 0.0,
    contribution_growth: float = 0.02,
    output_dir: Path | None = None,
) -> tuple[GoalSimulationSummary, GoalArtifacts]:
    """Run the full Monte Carlo workflow writing artefacts to disk."""

    summary = simulate_goals(
        goals,
        draws=draws,
        seed=seed,
        monthly_contribution=monthly_contribution,
        initial_wealth=initial_wealth,
        contribution_growth=contribution_growth,
    )
    artifacts = write_goal_artifacts(summary, output_dir=output_dir)
    return summary, artifacts


def load_goal_configs_from_yaml(path: Path | str) -> list[GoalConfig]:
    """Load goal configurations from a YAML file."""

    data = read_yaml(path)
    if isinstance(data, Mapping) and "goals" in data:
        payload = data["goals"]
    elif isinstance(data, Sequence):
        payload = data
    else:
        payload = []
    if payload is None:
        return []
    return load_goal_configs(payload)


def load_goal_parameters(path: Path | str) -> dict[str, float]:
    """Helper to load household parameters used by the CLI."""

    data = read_yaml(path)
    if not isinstance(data, Mapping):
        return {}
    household = data.get("household", {})
    if not isinstance(household, Mapping):
        return {}
    return {
        "monthly_contribution": float(household.get("contrib_monthly", 0.0)),
        "initial_wealth": float(household.get("initial_wealth", 0.0)),
        "contribution_growth": float(household.get("contribution_growth", 0.02)),
    }
