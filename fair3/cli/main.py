"""Command-line interface orchestrating the FAIR-III pipelines."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml

from fair3.engine.allocators import run_optimization_pipeline
from fair3.engine.brokers import available_brokers
from fair3.engine.estimates import run_estimate_pipeline
from fair3.engine.etl import TRPanelBuilder
from fair3.engine.execution import summarise_decision
from fair3.engine.factors import run_factor_pipeline
from fair3.engine.goals import (
    load_goal_configs_from_yaml,
    load_goal_parameters,
    run_goal_monte_carlo,
)
from fair3.engine.gui import launch_gui
from fair3.engine.ingest import available_sources, run_ingest
from fair3.engine.logging import configure_cli_logging, record_metrics
from fair3.engine.mapping import run_mapping_pipeline
from fair3.engine.qa import DemoQAConfig, run_demo_qa
from fair3.engine.regime import run_regime_pipeline
from fair3.engine.reporting import MonthlyReportInputs, generate_monthly_report
from fair3.engine.universe import run_universe_pipeline
from fair3.engine.utils.rand import generator_from_seed
from fair3.engine.validate import validate_configs

DESCRIPTION = "FAIR-III Portfolio Engine"


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # pragma: no cover - argparse validation
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DD date format") from exc


def _parse_timestamp(value: str) -> pd.Timestamp:
    """Parse CLI-provided timestamps with descriptive errors.

    Args:
        value: String value provided on the command line.

    Returns:
        Parsed :class:`pandas.Timestamp` value.

    Raises:
        argparse.ArgumentTypeError: If ``value`` cannot be interpreted as a timestamp.
    """

    try:
        return pd.Timestamp(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - argparse validation
        raise argparse.ArgumentTypeError(
            "Invalid timestamp. Use YYYY-MM-DD or ISO format."
        ) from exc


def _add_ingest_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    ingest = subparsers.add_parser("ingest", help="Download raw datasets")
    ingest.add_argument(
        "--source",
        required=True,
        choices=available_sources(),
        help="Data source to download",
    )
    ingest.add_argument(
        "--symbols",
        nargs="+",
        help="Optional list of source-specific symbols",
    )
    ingest.add_argument(
        "--from",
        dest="start_date",
        type=_parse_date,
        help="Earliest observation date (YYYY-MM-DD)",
    )


def _add_universe_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    universe = subparsers.add_parser(
        "universe",
        help="Aggrega universi broker, mapping OpenFIGI e suggerimenti sui provider",
    )
    universe.add_argument(
        "--brokers",
        nargs="+",
        choices=available_brokers(),
        help="Elenco opzionale di broker da includere (predefinito: tutti)",
    )
    universe.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data") / "clean" / "universe",
        help="Cartella in cui salvare gli artefatti aggregati della pipeline",
    )
    universe.add_argument(
        "--openfigi-key",
        dest="openfigi_key",
        help="Chiave API OpenFIGI facoltativa per arricchire i listing degli ISIN",
    )
    universe.add_argument(
        "--dry-run",
        action="store_true",
        help="Esegue la scoperta senza scrivere su disco",
    )


def _add_etl_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    etl = subparsers.add_parser("etl", help="Rebuild point-in-time clean panel")
    etl.add_argument("--rebuild", action="store_true", help="Run full rebuild of clean panel")
    etl.add_argument("--raw-root", default="data/raw", help=argparse.SUPPRESS)
    etl.add_argument("--clean-root", default="data/clean", help=argparse.SUPPRESS)
    etl.add_argument("--audit-root", default="audit", help=argparse.SUPPRESS)
    etl.add_argument("--base-currency", default="EUR", help="Base currency for conversion")
    etl.add_argument("--seed", type=int, default=0, help="Seed for deterministic feature ops")
    etl.add_argument("--trace", action="store_true", help="Emit verbose step information")


def _add_factors_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    factors = subparsers.add_parser("factors", help="Generate factor premia and diagnostics")
    factors.add_argument(
        "--clean-root",
        type=Path,
        default=Path("data") / "clean",
        help=argparse.SUPPRESS,
    )
    factors.add_argument("--artifacts-root", type=Path, help="Optional custom artifacts root")
    factors.add_argument("--audit-dir", type=Path, help="Optional audit directory override")
    factors.add_argument("--seed", type=int, default=0, help="Random seed for factor generation")
    factors.add_argument("--validate", action="store_true", help="Run factor validation suite")
    factors.add_argument(
        "--oos-splits",
        type=int,
        default=5,
        help="Out-of-sample splits for validation",
    )
    factors.add_argument("--embargo", type=int, default=5, help="Embargo length for CP-CV")


def _add_estimate_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    estimate = subparsers.add_parser("estimate", help="Estimate expected returns and covariance")
    estimate.add_argument("--artifacts-root", type=Path, help="Optional custom artifacts root")
    estimate.add_argument("--audit-dir", type=Path, help="Optional audit directory override")
    estimate.add_argument(
        "--thresholds",
        type=Path,
        default=Path("configs") / "thresholds.yml",
        help="Path to thresholds YAML",
    )
    estimate.add_argument(
        "--cv-splits",
        type=int,
        default=5,
        help="Cross-validation splits for ensemble",
    )
    estimate.add_argument("--seed", type=int, default=0, help="Random seed for ensemble")
    estimate.add_argument(
        "--sigma-engine",
        choices=("median_psd", "spd_median"),
        default="median_psd",
        help="Covariance consensus engine to employ",
    )


def _add_optimize_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    optimize = subparsers.add_parser("optimize", help="Run factor optimisation generators")
    optimize.add_argument("--artifacts-root", type=Path, help="Optional custom artifacts root")
    optimize.add_argument("--audit-dir", type=Path, help="Optional audit directory override")
    optimize.add_argument(
        "--params",
        type=Path,
        default=Path("configs") / "params.yml",
        help="Household parameters YAML",
    )
    optimize.add_argument(
        "--thresholds",
        type=Path,
        default=Path("configs") / "thresholds.yml",
        help="Threshold configuration YAML",
    )
    optimize.add_argument(
        "--generators",
        default="A,B,C,D",
        help="Comma-separated list of generators to run",
    )
    optimize.add_argument("--meta", action="store_true", help="Blend generators via meta-learner")


def _add_map_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    mapping = subparsers.add_parser("map", help="Map factor weights to instruments")
    mapping.add_argument("--artifacts-root", type=Path, help="Optional custom artifacts root")
    mapping.add_argument("--audit-dir", type=Path, help="Optional audit directory override")
    mapping.add_argument(
        "--clean-root",
        type=Path,
        default=Path("data") / "clean",
        help=argparse.SUPPRESS,
    )
    mapping.add_argument(
        "--thresholds",
        type=Path,
        default=Path("configs") / "thresholds.yml",
        help="Threshold configuration YAML",
    )
    mapping.add_argument("--window", type=int, help="Rolling window length for betas")
    mapping.add_argument(
        "--lambda-beta",
        type=float,
        default=1.0,
        help="Ridge penalty for beta regression",
    )
    mapping.add_argument(
        "--bootstrap",
        type=int,
        default=200,
        help="Bootstrap samples for beta confidence intervals",
    )
    mapping.add_argument("--hrp-intra", action="store_true", help="Apply intra-factor HRP baseline")
    mapping.add_argument("--adv-cap", type=float, help="ADV cap ratio for trade clipping")
    mapping.add_argument(
        "--te-factor-max",
        type=float,
        help="Maximum absolute deviation per factor exposure",
    )
    mapping.add_argument(
        "--tau-beta",
        type=float,
        help="Maximum CI80 width before shrinking instrument weights",
    )


def _add_regime_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    regime = subparsers.add_parser("regime", help="Estimate regime probabilities and hysteresis")
    regime.add_argument(
        "--clean-root",
        type=Path,
        default=Path("data") / "clean",
        help="Directory containing the clean PIT panel",
    )
    regime.add_argument(
        "--thresholds",
        type=Path,
        default=Path("configs") / "thresholds.yml",
        help="Path to thresholds configuration YAML",
    )
    regime.add_argument("--seed", type=int, default=0, help="Seed for deterministic regime engine")
    regime.add_argument(
        "--dry-run",
        action="store_true",
        help="Run analytics without triggering downstream execution",
    )
    regime.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory for regime artefacts",
    )
    regime.add_argument(
        "--trace",
        action="store_true",
        help="Print the tail of the regime probabilities for inspection",
    )


def _add_report_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    report = subparsers.add_parser("report", help="Generate reporting artefacts")
    report.add_argument(
        "--period",
        required=True,
        help="Reporting period in YYYY-MM:YYYY-MM format",
    )
    report.add_argument(
        "--monthly",
        action="store_true",
        help="Generate the monthly performance report",
    )
    report.add_argument(
        "--output-dir",
        type=Path,
        help="Optional custom output directory for artefacts",
    )
    report.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Seed for deterministic fan chart simulation",
    )


def _add_goals_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    goals = subparsers.add_parser("goals", help="Evaluate household goals via Monte Carlo")
    goals.add_argument("--draws", type=int, default=10_000, help="Number of Monte Carlo paths")
    goals.add_argument("--seed", type=int, default=0, help="Random seed for simulation")
    goals.add_argument(
        "--goals-config",
        type=Path,
        default=Path("configs/goals.yml"),
        help="Path to goals configuration YAML",
    )
    goals.add_argument(
        "--params",
        type=Path,
        default=Path("configs/params.yml"),
        help="Path to household parameter YAML",
    )
    goals.add_argument(
        "--monthly-contribution",
        type=float,
        help="Override monthly contribution amount",
    )
    goals.add_argument(
        "--initial-wealth",
        type=float,
        help="Override initial wealth level",
    )
    goals.add_argument(
        "--contribution-growth",
        type=float,
        help="Override annual contribution growth rate",
    )
    goals.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory for goal artefacts",
    )
    goals.add_argument(
        "--simulate",
        action="store_true",
        help="Run the Monte Carlo simulation and generate artefacts",
    )


def _add_execute_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    execute = subparsers.add_parser("execute", help="Evaluate execution decision gates")
    execute.add_argument(
        "--rebalance-date",
        required=True,
        dest="rebalance_date",
        type=_parse_date,
        help="Target rebalance date (YYYY-MM-DD)",
    )
    execute.add_argument(
        "--dry-run",
        action="store_true",
        help="Print decision breakdown without submitting orders",
    )
    execute.add_argument(
        "--tax-method",
        choices=["fifo", "lifo", "min_tax"],
        default="fifo",
        help="Select the tax lot matching method (default: fifo)",
    )


def _add_validate_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Attach the validate command used for configuration schema checks."""

    validate = subparsers.add_parser("validate", help="Validate YAML configuration files")
    validate.add_argument(
        "--params",
        type=Path,
        default=Path("configs") / "params.yml",
        help="Path to params.yml configuration",
    )
    validate.add_argument(
        "--thresholds",
        type=Path,
        default=Path("configs") / "thresholds.yml",
        help="Path to thresholds.yml configuration",
    )
    validate.add_argument(
        "--goals",
        type=Path,
        default=Path("configs") / "goals.yml",
        help="Path to goals.yml configuration",
    )
    validate.add_argument(
        "--verbose",
        action="store_true",
        help="Print the parsed configuration payloads on success",
    )


def _add_gui_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Attach the gui command that launches the optional PySide6 interface.

    Args:
        subparsers: Collection of subparsers that will receive the GUI command.

    Returns:
        None.
    """

    gui = subparsers.add_parser("gui", help="Launch the optional PySide6 orchestration GUI")
    gui.add_argument("--dry-run", action="store_true", help="Print configuration without launching")
    gui.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw"),
        help="Directory containing raw CSV downloads",
    )
    gui.add_argument(
        "--clean-root",
        type=Path,
        default=Path("data/clean"),
        help="Directory containing the clean PIT panel",
    )
    gui.add_argument(
        "--artifacts-root",
        type=Path,
        default=Path("artifacts"),
        help="Directory for pipeline artefacts",
    )
    gui.add_argument(
        "--audit-root",
        type=Path,
        default=Path("audit"),
        help="Directory for audit trail outputs",
    )
    gui.add_argument(
        "--thresholds",
        type=Path,
        default=Path("configs") / "thresholds.yml",
        help="Threshold configuration used by estimate and regime steps",
    )
    gui.add_argument(
        "--params",
        type=Path,
        default=Path("configs") / "params.yml",
        help="Household parameters used by the goal engine",
    )
    gui.add_argument(
        "--goals",
        type=Path,
        default=Path("configs") / "goals.yml",
        help="Goal configuration used by the Monte Carlo simulation",
    )
    gui.add_argument(
        "--report",
        type=Path,
        help="Optional report path pre-filled in the GUI",
    )
    gui.add_argument(
        "--universe-dir",
        type=Path,
        default=Path("data") / "clean" / "universe",
        help="Directory used to persist broker universe artefacts",
    )
    gui.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("artifacts") / "reports",
        help="Directory where generated reports are stored",
    )


def _add_qa_subparser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Attach the qa command that runs the deterministic QA pipeline.

    Args:
        subparsers: Collection of CLI subparsers to which the QA command is added.

    Returns:
        None.
    """

    qa = subparsers.add_parser("qa", help="Run deterministic end-to-end QA")
    qa.add_argument("--label", default="demo", help="Label used for QA artefact folders")
    qa.add_argument(
        "--output-dir",
        type=Path,
        help="Optional directory where QA artefacts will be stored",
    )
    qa.add_argument(
        "--start",
        type=_parse_timestamp,
        default=pd.Timestamp("2018-01-01"),
        help="Start date for the synthetic QA dataset (YYYY-MM-DD)",
    )
    qa.add_argument(
        "--end",
        type=_parse_timestamp,
        default=pd.Timestamp("2021-12-31"),
        help="End date for the synthetic QA dataset (YYYY-MM-DD)",
    )
    qa.add_argument("--seed", type=int, help="Optional seed override for QA runs")
    qa.add_argument(
        "--draws",
        type=int,
        default=256,
        help="Number of bootstrap draws for robustness QA",
    )
    qa.add_argument(
        "--block-size",
        dest="block_size",
        type=int,
        default=45,
        help="Bootstrap block size for robustness QA",
    )
    qa.add_argument(
        "--cv-splits",
        type=int,
        default=3,
        help="Cross-validation folds for stochastic estimators",
    )
    qa.add_argument(
        "--validate-factors",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Toggle factor validation during QA (disabled by default)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fair3", description=DESCRIPTION)
    parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Display tqdm progress bars for long-running steps",
    )
    parser.add_argument(
        "--json-logs",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Mirror logs to artifacts/audit/fair3.log in JSON format",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_validate_subparser(sub)
    _add_ingest_subparser(sub)
    _add_universe_subparser(sub)
    _add_etl_subparser(sub)
    _add_report_subparser(sub)
    _add_goals_subparser(sub)
    _add_execute_subparser(sub)
    _add_factors_subparser(sub)
    _add_estimate_subparser(sub)
    _add_optimize_subparser(sub)
    _add_map_subparser(sub)
    _add_regime_subparser(sub)
    _add_gui_subparser(sub)
    _add_qa_subparser(sub)
    return parser


def _handle_ingest(args: argparse.Namespace) -> None:
    result = run_ingest(
        args.source,
        symbols=args.symbols,
        start=args.start_date,
        progress=args.progress,
    )
    symbols: Iterable[str] = args.symbols if args.symbols is not None else ()
    symbol_list = list(symbols)
    symbol_str = ",".join(symbol_list) if symbol_list else "default"
    print(
        f"[fair3] ingest source={result.source} symbols={symbol_str} "
        f"rows={len(result.data)} path={result.path}"
    )
    record_metrics(
        "ingest_rows",
        float(len(result.data)),
        {"source": result.source, "symbols": symbol_str or "default"},
    )


def _handle_universe(args: argparse.Namespace) -> None:
    brokers = tuple(args.brokers) if args.brokers else None
    result = run_universe_pipeline(
        brokers=brokers,
        output_dir=args.output_dir,
        openfigi_api_key=args.openfigi_key,
        dry_run=args.dry_run,
    )
    provider_usage = ",".join(
        f"{source}:{count}" for source, count in result.metadata.get("provider_usage", ())
    )
    summary = {
        "brokers": ",".join(result.brokers),
        "instruments": result.metadata.get("instrument_count", 0),
        "providers": provider_usage or "none",
        "output": result.broker_universe_path,
    }
    print("[fair3] universe " + " ".join(f"{key}={value}" for key, value in summary.items()))
    record_metrics(
        "universe_instruments",
        float(result.metadata.get("instrument_count", 0)),
        {"brokers": summary["brokers"], "providers": summary["providers"]},
    )


def _handle_etl(args: argparse.Namespace) -> None:
    if not args.rebuild:
        raise SystemExit("--rebuild flag required for ETL")
    builder = TRPanelBuilder(
        raw_root=args.raw_root,
        clean_root=args.clean_root,
        audit_root=args.audit_root,
        base_currency=args.base_currency,
    )
    artifacts = builder.build(seed=args.seed, trace=args.trace)
    summary = (
        f"[fair3] etl rows={artifacts.rows} symbols={len(artifacts.symbols)} "
        f"panel={artifacts.panel_path} checksum={artifacts.checksum} "
        f"qa={artifacts.qa_path}"
    )
    print(summary)


def _parse_period(value: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start_str, end_str = value.split(":", maxsplit=1)
    except ValueError as exc:  # pragma: no cover - argparse validation
        raise argparse.ArgumentTypeError("Expected period format YYYY-MM:YYYY-MM") from exc
    try:
        start = pd.Timestamp(start_str) + pd.offsets.MonthEnd(0)
        end = pd.Timestamp(end_str) + pd.offsets.MonthEnd(0)
    except (TypeError, ValueError) as exc:  # pragma: no cover - pandas parsing
        raise argparse.ArgumentTypeError("Invalid YYYY-MM period specification") from exc
    if start > end:
        raise argparse.ArgumentTypeError("Period start must be before end")
    return start, end


def _synthetic_monthly_inputs(
    start: pd.Timestamp, end: pd.Timestamp, seed: int
) -> MonthlyReportInputs:
    months = pd.date_range(start=start, end=end, freq=pd.offsets.MonthEnd())
    rng = generator_from_seed(seed)
    returns = pd.Series(rng.normal(0.005, 0.02, len(months)), index=months)
    instruments = ["EQT_ETF", "BND_ETF", "ALT_ETF", "CASH"]
    raw_weights = rng.uniform(0, 1, size=(len(months), len(instruments)))
    weights = pd.DataFrame(raw_weights, index=months, columns=instruments)
    weights = weights.div(weights.sum(axis=1), axis=0)

    factor_cols = ["Growth", "Value", "Rates"]
    factor_attr = pd.DataFrame(
        rng.normal(0.001, 0.01, size=(len(months), len(factor_cols))),
        index=months,
        columns=factor_cols,
    )
    instr_attr = pd.DataFrame(
        rng.normal(0.001, 0.008, size=(len(months), len(instruments))),
        index=months,
        columns=instruments,
    )
    instrument_returns = pd.DataFrame(
        rng.normal(0.004, 0.015, size=(len(months), len(instruments))),
        index=months,
        columns=instruments,
    )
    factor_returns = pd.DataFrame(
        rng.normal(0.002, 0.01, size=(len(months), len(factor_cols))),
        index=months,
        columns=factor_cols,
    )
    bootstrap_metrics = pd.DataFrame(
        {
            "max_drawdown": rng.uniform(-0.35, -0.1, size=256),
            "cagr": rng.normal(0.05, 0.01, size=256),
        }
    )
    thresholds = {
        "max_drawdown_threshold": -0.25,
        "cagr_target": 0.03,
        "max_drawdown_exceedance": 0.05,
        "cagr_alpha": 0.05,
    }
    turnover = pd.Series(rng.uniform(0.0, 0.15, len(months)), index=months)
    costs = pd.Series(rng.uniform(0.0, 0.001, len(months)), index=months)
    taxes = pd.Series(rng.uniform(0.0, 0.0005, len(months)), index=months)
    compliance = {
        "ucits_only": True,
        "no_trade_band_respected": bool(rng.uniform() > 0.05),
        "audit_complete": True,
    }
    cluster_map = {
        "Equity": ["EQT_ETF"],
        "Rates": ["BND_ETF"],
        "Alternatives": ["ALT_ETF"],
        "Liquidity": ["CASH"],
    }
    return MonthlyReportInputs(
        returns=returns,
        weights=weights,
        factor_contributions=factor_attr,
        instrument_contributions=instr_attr,
        turnover=turnover,
        costs=costs,
        taxes=taxes,
        compliance_flags=compliance,
        cluster_map=cluster_map,
        instrument_returns=instrument_returns,
        factor_returns=factor_returns,
        bootstrap_metrics=bootstrap_metrics,
        thresholds=thresholds,
    )


def _handle_factors(args: argparse.Namespace) -> None:
    result = run_factor_pipeline(
        clean_root=args.clean_root,
        artifacts_root=args.artifacts_root,
        audit_dir=args.audit_dir,
        seed=args.seed,
        validate=args.validate,
        oos_splits=args.oos_splits,
        embargo=args.embargo,
    )
    print(
        f"[fair3] factors factors={result.factors_path} "
        f"orthogonal={result.orthogonal_path} validation={result.validation_path}"
    )


def _handle_estimate(args: argparse.Namespace) -> None:
    result = run_estimate_pipeline(
        artifacts_root=args.artifacts_root,
        thresholds_path=args.thresholds,
        audit_dir=args.audit_dir,
        cv_splits=args.cv_splits,
        seed=args.seed,
        sigma_engine=args.sigma_engine,
    )
    print(
        f"[fair3] estimate mu_post={result.mu_post_path} "
        f"sigma={result.sigma_path} blend={result.blend_log_path}"
    )


def _handle_optimize(args: argparse.Namespace) -> None:
    generators = [item.strip() for item in args.generators.split(",") if item.strip()]
    result = run_optimization_pipeline(
        artifacts_root=args.artifacts_root,
        params_path=args.params,
        thresholds_path=args.thresholds,
        audit_dir=args.audit_dir,
        generators=generators or ("A", "B", "C", "D"),
        use_meta=args.meta,
    )
    meta_path = result.meta_weights_path if result.meta_weights_path is not None else "-"
    print(
        f"[fair3] optimize allocation={result.allocation_path} "
        f"diagnostics={result.diagnostics_path} meta={meta_path}"
    )


def _handle_map(args: argparse.Namespace) -> None:
    result = run_mapping_pipeline(
        artifacts_root=args.artifacts_root,
        clean_root=args.clean_root,
        thresholds_path=args.thresholds,
        audit_dir=args.audit_dir,
        window=args.window,
        lambda_beta=args.lambda_beta,
        bootstrap_samples=args.bootstrap,
        use_hrp_intra=args.hrp_intra,
        adv_cap_ratio=args.adv_cap,
        te_factor_max=args.te_factor_max,
        tau_beta=args.tau_beta,
    )
    print(
        f"[fair3] map instruments={result.instrument_weights_path} "
        f"betas={result.beta_path} summary={result.summary_path}"
    )


def _handle_regime(args: argparse.Namespace) -> None:
    result = run_regime_pipeline(
        clean_root=args.clean_root,
        thresholds_path=args.thresholds,
        output_dir=args.output_dir,
        seed=args.seed,
        dry_run=args.dry_run,
        trace=args.trace,
    )
    latest = result.scores.iloc[-1]
    regime_cfg = result.thresholds if isinstance(result.thresholds, Mapping) else {}
    on = float(regime_cfg.get("on", 0.65))
    off = float(regime_cfg.get("off", 0.45))
    mode = "dry-run" if args.dry_run else "live"
    print(
        f"[fair3] regime mode={mode} p_crisis={latest['p_crisis']:.3f} "
        f"on={on:.2f} off={off:.2f} path={result.probabilities_path}"
    )
    record_metrics(
        "regime_p_crisis",
        float(latest["p_crisis"]),
        {"mode": mode, "path": str(result.probabilities_path)},
    )


def _handle_report(args: argparse.Namespace) -> None:
    start, end = _parse_period(args.period)
    label = f"{start.strftime('%Y-%m')}:{end.strftime('%Y-%m')}"
    if not args.monthly:
        print(f"[fair3] report period={label} mode=summary (monthly flag required)")
        return
    inputs = _synthetic_monthly_inputs(start, end, args.seed)
    artifacts = generate_monthly_report(
        inputs,
        period_label=label,
        output_dir=args.output_dir,
        seed=args.seed,
    )
    print(
        f"[fair3] report monthly period={label} metrics={artifacts.metrics_csv} "
        f"fan_chart={artifacts.fan_chart} acceptance={artifacts.acceptance_json} "
        f"pdf={artifacts.report_pdf}"
    )


def _handle_execute(args: argparse.Namespace) -> None:
    breakdown = summarise_decision(
        drift_ok=False,
        eb_lb=0.0,
        cost=0.0,
        tax=0.0,
        turnover_ok=True,
    )
    status = "rebalance" if breakdown.execute else "hold"
    prefix = "[fair3] execute"
    tax_method = args.tax_method
    if args.dry_run:
        print(
            f"{prefix} dry-run date={args.rebalance_date.isoformat()} "
            f"decision={status} tax_method={tax_method} net={breakdown.net_benefit:.4f}"
        )
    else:
        print(
            f"{prefix} date={args.rebalance_date.isoformat()} decision={status} "
            f"tax_method={tax_method} controller=placeholder"
        )


def _handle_validate(args: argparse.Namespace) -> None:
    """Validate configuration files and report diagnostics to stdout."""

    summary = validate_configs(
        params_path=args.params,
        thresholds_path=args.thresholds,
        goals_path=args.goals,
    )
    if args.verbose and summary.configs:
        for label, payload in summary.configs.items():
            rendered = yaml.safe_dump(payload, sort_keys=True)
            print(f"[fair3] validate {label}\n{rendered}", end="")
    for warning in summary.warnings:
        print(f"[fair3] validate warning: {warning}")
    if summary.errors:
        for error in summary.errors:
            print(f"[fair3] validate error: {error}")
        raise SystemExit(1)
    print("[fair3] validate status=ok")


def _handle_gui(args: argparse.Namespace) -> None:
    """Launch the optional PySide6 GUI if available.

    Args:
        args: Parsed CLI arguments for the gui command.

    Returns:
        None.
    """

    config = {
        "raw_root": args.raw_root,
        "clean_root": args.clean_root,
        "artifacts_root": args.artifacts_root,
        "audit_root": args.audit_root,
        "thresholds": args.thresholds,
        "params": args.params,
        "goals": args.goals,
        "universe_root": args.universe_dir,
        "report_root": args.reports_dir,
    }
    if args.report is not None:
        config["report_path"] = args.report
    if args.dry_run:
        print(
            "[fair3] gui dry-run "
            f"raw_root={args.raw_root} clean_root={args.clean_root} "
            f"artifacts_root={args.artifacts_root} universe_dir={args.universe_dir} "
            f"report_root={args.reports_dir}"
        )
        return
    launch_gui(config)


def _handle_qa(args: argparse.Namespace) -> None:
    """Run the deterministic QA pipeline and display artefact locations.

    Args:
        args: Parsed CLI arguments produced by :func:`_add_qa_subparser`.

    Returns:
        None. The function prints a human-readable summary and records metrics.
    """

    if args.start > args.end:
        raise SystemExit("--start must be on or before --end")
    config = DemoQAConfig(
        label=args.label,
        start=pd.Timestamp(args.start),
        end=pd.Timestamp(args.end),
        output_dir=args.output_dir,
        seed=args.seed,
        validate_factors=args.validate_factors,
        cv_splits=max(2, args.cv_splits),
        robustness_draws=max(1, args.draws),
        robustness_block_size=max(1, args.block_size),
    )
    result = run_demo_qa(config=config)
    record_metrics("qa_acceptance_passed", float(result.acceptance_passed), {"label": config.label})
    record_metrics("qa_robustness_passed", float(result.robustness_passed), {"label": config.label})
    status = "PASS" if result.acceptance_passed and result.robustness_passed else "CHECK"
    print(
        "[fair3] qa "
        f"label={config.label} status={status} "
        f"report={result.report_pdf} acceptance={result.acceptance_passed} "
        f"robustness={result.robustness_passed}"
    )


def _handle_goals(args: argparse.Namespace) -> None:
    goals = load_goal_configs_from_yaml(args.goals_config)
    if not goals:
        raise SystemExit("No goals configured")
    parameters = load_goal_parameters(args.params)
    if args.monthly_contribution is not None:
        parameters = replace(parameters, monthly_contribution=float(args.monthly_contribution))
    if args.initial_wealth is not None:
        parameters = replace(parameters, initial_wealth=float(args.initial_wealth))
    if args.contribution_growth is not None:
        parameters = replace(parameters, contribution_growth=float(args.contribution_growth))
    draws = max(1, int(args.draws))
    summary, artifacts = run_goal_monte_carlo(
        goals,
        draws=draws,
        seed=int(args.seed),
        parameters=parameters,
        output_dir=args.output_dir,
    )
    if not args.simulate:
        print(
            f"[fair3] goals simulate flag not provided; configured_goals={len(goals)} "
            f"investor={parameters.investor}"
        )
    fragments = [
        f"{row.goal}={row.probability:.3f}" for row in summary.results.itertuples(index=False)
    ]
    result_str = ",".join(fragments) if fragments else "none"
    print(
        f"[fair3] goals draws={summary.draws} investor={parameters.investor} "
        f"weighted={summary.weighted_probability:.3f} results={result_str} "
        f"pdf={artifacts.report_pdf} fan={artifacts.fan_chart_csv}"
    )


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_cli_logging(json_logs=bool(args.json_logs))
    if args.cmd == "ingest":
        _handle_ingest(args)
    elif args.cmd == "universe":
        _handle_universe(args)
    elif args.cmd == "etl":
        _handle_etl(args)
    elif args.cmd == "report":
        _handle_report(args)
    elif args.cmd == "goals":
        _handle_goals(args)
    elif args.cmd == "execute":
        _handle_execute(args)
    elif args.cmd == "factors":
        _handle_factors(args)
    elif args.cmd == "estimate":
        _handle_estimate(args)
    elif args.cmd == "optimize":
        _handle_optimize(args)
    elif args.cmd == "map":
        _handle_map(args)
    elif args.cmd == "regime":
        _handle_regime(args)
    elif args.cmd == "gui":
        _handle_gui(args)
    elif args.cmd == "qa":
        _handle_qa(args)
    elif args.cmd == "validate":
        _handle_validate(args)
    else:
        print(f"[fair3] command = {args.cmd}")


if __name__ == "__main__":
    main()
