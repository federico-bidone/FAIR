from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from fair3.engine.allocators import run_optimization_pipeline
from fair3.engine.estimates import run_estimate_pipeline
from fair3.engine.etl import TRPanelBuilder
from fair3.engine.execution import summarise_decision
from fair3.engine.factors import run_factor_pipeline
from fair3.engine.goals import (
    load_goal_configs_from_yaml,
    load_goal_parameters,
    run_goal_monte_carlo,
)
from fair3.engine.ingest import available_sources, run_ingest
from fair3.engine.mapping import run_mapping_pipeline
from fair3.engine.reporting import MonthlyReportInputs, generate_monthly_report
from fair3.engine.utils.rand import generator_from_seed

DESCRIPTION = "FAIR-III Portfolio Engine"


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:  # pragma: no cover - argparse validation
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DD date format") from exc


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fair3", description=DESCRIPTION)
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_ingest_subparser(sub)
    _add_etl_subparser(sub)
    _add_report_subparser(sub)
    _add_goals_subparser(sub)
    _add_execute_subparser(sub)
    _add_factors_subparser(sub)
    _add_estimate_subparser(sub)
    _add_optimize_subparser(sub)
    _add_map_subparser(sub)
    return parser


def _handle_ingest(args: argparse.Namespace) -> None:
    result = run_ingest(args.source, symbols=args.symbols, start=args.start_date)
    symbols: Iterable[str] = args.symbols if args.symbols is not None else ()
    symbol_list = list(symbols)
    symbol_str = ",".join(symbol_list) if symbol_list else "default"
    print(
        f"[fair3] ingest source={result.source} symbols={symbol_str} "
        f"rows={len(result.data)} path={result.path}"
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
        f"prices={artifacts.prices_path} returns={artifacts.returns_path} "
        f"features={artifacts.features_path} qa={artifacts.qa_path}"
    )
    print(summary)


def _parse_period(value: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    try:
        start_str, end_str = value.split(":", maxsplit=1)
    except ValueError as exc:  # pragma: no cover - argparse validation
        raise argparse.ArgumentTypeError("Expected period format YYYY-MM:YYYY-MM") from exc
    try:
        start = pd.Period(start_str, freq="M").to_timestamp("M")
        end = pd.Period(end_str, freq="M").to_timestamp("M")
    except ValueError as exc:  # pragma: no cover - pandas parsing
        raise argparse.ArgumentTypeError("Invalid YYYY-MM period specification") from exc
    if start > end:
        raise argparse.ArgumentTypeError("Period start must be before end")
    return start, end


def _synthetic_monthly_inputs(
    start: pd.Timestamp, end: pd.Timestamp, seed: int
) -> MonthlyReportInputs:
    months = pd.period_range(start=start, end=end, freq="M").to_timestamp("M")
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
    )
    print(
        f"[fair3] map instruments={result.instrument_weights_path} "
        f"betas={result.beta_path} summary={result.summary_path}"
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
        f"fan_chart={artifacts.fan_chart}"
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
    if args.dry_run:
        print(
            f"{prefix} dry-run date={args.rebalance_date.isoformat()} "
            f"decision={status} net={breakdown.net_benefit:.4f}"
        )
    else:
        print(
            f"{prefix} date={args.rebalance_date.isoformat()} decision={status} "
            "controller=placeholder"
        )


def _handle_goals(args: argparse.Namespace) -> None:
    goals = load_goal_configs_from_yaml(args.goals_config)
    if not goals:
        raise SystemExit("No goals configured")
    params = load_goal_parameters(args.params)
    monthly_contribution = (
        float(args.monthly_contribution)
        if args.monthly_contribution is not None
        else params.get("monthly_contribution", 0.0)
    )
    initial_wealth = (
        float(args.initial_wealth)
        if args.initial_wealth is not None
        else params.get("initial_wealth", 0.0)
    )
    contribution_growth = (
        float(args.contribution_growth)
        if args.contribution_growth is not None
        else params.get("contribution_growth", 0.02)
    )
    draws = max(1, int(args.draws))
    summary, artifacts = run_goal_monte_carlo(
        goals,
        draws=draws,
        seed=int(args.seed),
        monthly_contribution=monthly_contribution,
        initial_wealth=initial_wealth,
        contribution_growth=contribution_growth,
        output_dir=args.output_dir,
    )
    fragments = [
        f"{row.goal}={row.probability:.3f}" for row in summary.results.itertuples(index=False)
    ]
    result_str = ",".join(fragments) if fragments else "none"
    print(
        f"[fair3] goals draws={summary.draws} weighted={summary.weighted_probability:.3f} "
        f"results={result_str} pdf={artifacts.report_pdf}"
    )


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "ingest":
        _handle_ingest(args)
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
    else:
        print(f"[fair3] command = {args.cmd}")


if __name__ == "__main__":
    main()
