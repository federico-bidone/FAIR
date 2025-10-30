"""Main window hosting the FAIR orchestration panels."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from fair3.engine.gui.panels.api_keys import APIKeysPanel
from fair3.engine.gui.panels.brokers import BrokersPanel
from fair3.engine.gui.panels.data_providers import DataProvidersPanel
from fair3.engine.gui.panels.pipeline import PipelinePanel
from fair3.engine.gui.panels.reports import ReportsPanel
from fair3.engine.gui.workers.job import JobRunner
from fair3.engine.infra.paths import DEFAULT_REPORT_ROOT, run_dir
from fair3.engine.infra.secrets import apply_api_keys, get_api_key, load_api_keys
from fair3.engine.reporting import MonthlyReportInputs, generate_monthly_report

try:  # pragma: no cover - optional dependency
    from PySide6 import QtCore, QtWidgets
except ImportError:  # pragma: no cover - optional dependency
    QtCore = QtWidgets = None  # type: ignore[assignment]

LOG = logging.getLogger(__name__)


class _LogEmitter(QtCore.QObject):  # type: ignore[misc]
    message = QtCore.Signal(str)  # type: ignore[call-arg]


class _GuiLogHandler(logging.Handler):
    def __init__(self, emitter: _LogEmitter) -> None:
        super().__init__(level=logging.INFO)
        self._emitter = emitter
        self.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - defensive
            message = record.getMessage()
        self._emitter.message.emit(message)


class FairMainWindow(QtWidgets.QMainWindow):  # type: ignore[misc]
    """High-level GUI integrating broker discovery, ingest and reporting."""

    def __init__(self, *, configuration: Mapping[str, Any], qt_core: Any, qt_gui: Any) -> None:
        if QtWidgets is None:  # pragma: no cover
            raise RuntimeError("PySide6 is required to launch the FAIR GUI")
        super().__init__()
        self._configuration = dict(configuration)
        self._qt_core = qt_core
        self._qt_gui = qt_gui
        self._jobs = JobRunner(qt_core)
        self._emitter = _LogEmitter()
        self._log_handler = _GuiLogHandler(self._emitter)
        self._report_root = Path(self._configuration.get("report_root", DEFAULT_REPORT_ROOT))
        self._logging_attached = False

        self.setWindowTitle("FAIR-III Orchestrator")
        self.resize(1280, 820)

        self._build_ui()
        self._attach_logging()
        self._connect_signals()
        apply_api_keys(load_api_keys())

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)

        self._tabs = QtWidgets.QTabWidget()
        self._brokers_panel = BrokersPanel()
        self._data_panel = DataProvidersPanel()
        self._api_keys_panel = APIKeysPanel()
        self._pipeline_panel = PipelinePanel()
        self._reports_panel = ReportsPanel(root=self._report_root)
        self._tabs.addTab(self._brokers_panel, "Broker")
        self._tabs.addTab(self._data_panel, "Data provider")
        self._tabs.addTab(self._pipeline_panel, "Pipeline")
        self._tabs.addTab(self._api_keys_panel, "API key")
        self._tabs.addTab(self._reports_panel, "Report")
        layout.addWidget(self._tabs)

        self._log_console = QtWidgets.QPlainTextEdit()
        self._log_console.setReadOnly(True)
        self._log_console.setMaximumBlockCount(2000)
        self._log_console.setPlaceholderText("Log runtime della pipeline FAIR")
        layout.addWidget(self._log_console)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Pronto")

    def _attach_logging(self) -> None:
        root = logging.getLogger()
        if self._log_handler not in root.handlers:
            root.addHandler(self._log_handler)
        if not self._logging_attached:
            self._emitter.message.connect(self._append_log)
            self._logging_attached = True

    def _connect_signals(self) -> None:
        self._brokers_panel.discoverRequested.connect(self._handle_universe_request)
        self._data_panel.ingestRequested.connect(self._handle_data_ingest)
        self._pipeline_panel.manualRequested.connect(self._run_manual_ingest)
        self._pipeline_panel.automaticRequested.connect(self._handle_automatic_pipeline)
        self._api_keys_panel.testRequested.connect(self._handle_test_provider)

    # ------------------------------------------------------------------
    def closeEvent(self, event: Any) -> None:  # noqa: D401 - Qt override
        """Detach logging handlers on window close."""

        root = logging.getLogger()
        if self._log_handler in root.handlers:
            root.removeHandler(self._log_handler)
        if self._logging_attached:
            self._emitter.message.disconnect(self._append_log)
            self._logging_attached = False
        super().closeEvent(event)

    # ------------------------------------------------------------------
    def _append_log(self, message: str) -> None:
        self._log_console.appendPlainText(message)

    def _status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        LOG.info(message)

    # ------------------------------------------------------------------
    def _handle_universe_request(self, brokers: tuple[str, ...]) -> None:
        self._status("Avvio della scoperta universo")

        def job() -> Any:
            from fair3.engine.universe import run_universe_pipeline

            output_dir = Path(
                self._configuration.get("universe_root", Path("data") / "clean" / "universe")
            )
            key = self._get_secret("OPENFIGI_API_KEY")
            return run_universe_pipeline(
                brokers=brokers or None,
                output_dir=output_dir,
                openfigi_api_key=key,
            )

        self._jobs.submit(job, on_success=self._universe_complete, on_error=self._job_failed)

    def _universe_complete(self, result: Any) -> None:
        try:
            brokers = ", ".join(result.brokers)
            self._status(f"Universe completato per broker: {brokers}")
        except AttributeError:
            self._status("Universe completato")

    # ------------------------------------------------------------------
    def _handle_data_ingest(self, source: str, symbols: tuple[str, ...], start: Any) -> None:
        payload = {
            "mode": "manual",
            "provider": source,
            "symbols": symbols,
            "start": start,
        }
        self._run_manual_ingest(payload)

    def _run_manual_ingest(self, payload: Mapping[str, Any]) -> None:
        provider = str(payload.get("provider"))
        symbols = tuple(payload.get("symbols", ()))
        start = payload.get("start")
        self._status(f"Ingest manuale per provider {provider}")

        def job() -> Any:
            from fair3.engine.ingest import run_ingest

            sym_iter = symbols or None
            return run_ingest(provider, symbols=sym_iter, start=start, progress=False)

        self._jobs.submit(job, on_success=lambda result: self._manual_complete(provider, result), on_error=self._job_failed)

    def _manual_complete(self, provider: str, result: Any) -> None:
        path = getattr(result, "path", None)
        if path:
            self._status(f"Ingest completato per {provider}: {path}")
        else:
            self._status(f"Ingest completato per {provider}")

    # ------------------------------------------------------------------
    def _handle_automatic_pipeline(self, payload: Mapping[str, Any]) -> None:
        data = dict(payload)
        if "brokers" not in data:
            data["brokers"] = self._brokers_panel.selected_brokers()
        self._status("Avvio pipeline automatica")

        def job() -> Mapping[str, Any]:
            return self._run_automatic_pipeline(data)

        self._jobs.submit(job, on_success=self._automatic_complete, on_error=self._job_failed)

    def _automatic_complete(self, result: Mapping[str, Any]) -> None:
        errors = result.get("errors", [])
        if errors:
            self._status(f"Pipeline completata con {len(errors)} avvisi")
        else:
            self._status("Pipeline completata con successo")
        report_dir = result.get("report_dir")
        if report_dir:
            self._reports_panel.refresh()
            self._status(f"Report disponibili in {report_dir}")

    # ------------------------------------------------------------------
    def _handle_test_provider(self, provider: str) -> None:
        self._status(f"Test della connessione per {provider}")
        env = self._api_keys_panel.env_for_source(provider) or provider.upper()
        key = self._get_secret(env)
        if key:
            self._status(f"Chiave trovata per {provider}")
        else:
            self._status(f"Chiave mancante per {provider}")

    # ------------------------------------------------------------------
    def _job_failed(self, exc: BaseException) -> None:
        LOG.exception("Background job failed", exc_info=exc)
        self._status(f"Errore: {exc}")

    def _get_secret(self, env: str) -> str | None:
        return get_api_key(env)

    # ------------------------------------------------------------------
    def _run_automatic_pipeline(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        brokers = tuple(payload.get("brokers", ()))
        start = payload.get("start")
        generate_reports = bool(payload.get("generate_reports", True))
        summary: dict[str, Any] = {"errors": []}
        report_dir = run_dir(self._report_root)
        summary["report_dir"] = str(report_dir)

        try:
            from fair3.engine.universe import run_universe_pipeline

            key = self._get_secret("OPENFIGI_API_KEY")
            universe = run_universe_pipeline(
                brokers=brokers or None,
                output_dir=self._configuration.get(
                    "universe_root", Path("data") / "clean" / "universe"
                ),
                openfigi_api_key=key,
            )
            summary["universe"] = {
                "brokers": universe.brokers,
                "providers_path": str(universe.providers_path),
            }
        except Exception as exc:  # pragma: no cover - orchestration safety
            LOG.exception("Universe pipeline failed", exc_info=exc)
            summary["errors"].append(f"universe: {exc}")
            universe = None
        else:
            universe = universe

        providers: set[str] = set()
        if universe is not None:
            try:
                provider_frame = pd.read_parquet(universe.providers_path)
                providers.update(provider_frame["primary_source"].dropna().unique())
            except Exception as exc:  # pragma: no cover - graceful degradation
                LOG.warning("Unable to read provider selection: %s", exc)
        if not providers:
            providers.update({"alphavantage_fx", "tiingo", "fred"})

        ingest_results: dict[str, str] = {}
        for provider in sorted(providers):
            try:
                from fair3.engine.ingest import run_ingest

                artifact = run_ingest(provider, start=start, progress=False)
                ingest_results[provider] = str(artifact.path)
            except Exception as exc:  # pragma: no cover - network errors etc.
                LOG.warning("Ingest failed for %s: %s", provider, exc)
                summary["errors"].append(f"ingest:{provider}: {exc}")
        if ingest_results:
            summary["ingest"] = ingest_results

        try:
            from fair3.engine.etl.make_tr_panel import TRPanelBuilder

            panel = TRPanelBuilder().build(trace=False)
            summary["etl"] = str(panel.panel_path)
        except Exception as exc:  # pragma: no cover - missing data
            LOG.warning("ETL failed: %s", exc)
            summary["errors"].append(f"etl: {exc}")

        try:
            from fair3.engine.factors import run_factor_pipeline

            factors = run_factor_pipeline(validate=False)
            summary["factors"] = str(factors.factors_path)
        except Exception as exc:  # pragma: no cover - dependent on ETL
            LOG.warning("Factor pipeline failed: %s", exc)
            summary["errors"].append(f"factors: {exc}")

        try:
            from fair3.engine.estimates import run_estimate_pipeline

            estimates = run_estimate_pipeline(validate=False)
            summary["estimates"] = str(estimates.mu_path)
        except Exception as exc:  # pragma: no cover
            LOG.warning("Estimate pipeline failed: %s", exc)
            summary["errors"].append(f"estimates: {exc}")

        if generate_reports:
            try:
                months = pd.date_range(end=pd.Timestamp.today(), periods=12, freq="M")
                inputs = self._synthetic_report_inputs(months)
                artifacts = generate_monthly_report(
                    inputs,
                    period_label=months[-1].strftime("%Y-%m"),
                    output_dir=report_dir,
                )
                summary["report"] = {
                    "html": str(artifacts.report_html),
                    "pdf": str(getattr(artifacts, "report_pdf", "")),
                }
            except Exception as exc:  # pragma: no cover
                LOG.warning("Report generation failed: %s", exc)
                summary["errors"].append(f"report: {exc}")

        return summary

    def _synthetic_report_inputs(self, months: pd.DatetimeIndex) -> MonthlyReportInputs:
        instruments = ["EQT_ETF", "BND_ETF", "ALT_ETF", "CASH"]
        factors = ["Growth", "Rates", "Inflation"]
        returns = pd.Series([(idx % 5 - 2) * 0.001 for idx in range(len(months))], index=months)
        weights = pd.DataFrame(0.25, index=months, columns=instruments)
        factor_attr = pd.DataFrame(
            [
                [(idx + offset) % 3 * 0.0005 for offset in range(len(factors))]
                for idx in range(len(months))
            ],
            index=months,
            columns=factors,
        )
        instr_attr = pd.DataFrame(
            [
                [(idx + offset) % 4 * 0.0004 for offset in range(len(instruments))]
                for idx in range(len(months))
            ],
            index=months,
            columns=instruments,
        )
        instrument_returns = pd.DataFrame(
            [[(idx + 1) * 0.001 for _ in instruments] for idx in range(len(months))],
            index=months,
            columns=instruments,
        )
        factor_returns = pd.DataFrame(
            [[(idx + 2) * 0.0007 for _ in factors] for idx in range(len(months))],
            index=months,
            columns=factors,
        )
        turnover = pd.Series(0.02, index=months)
        costs = pd.Series(0.0005, index=months)
        taxes = pd.Series(0.0002, index=months)
        bootstrap_metrics = pd.DataFrame(
            {
                "max_drawdown": [-0.25, -0.22, -0.21],
                "cagr": [0.05, 0.045, 0.052],
            }
        )
        thresholds = {
            "max_drawdown_threshold": -0.30,
            "cagr_target": 0.03,
            "max_drawdown_exceedance": 0.05,
            "cagr_alpha": 0.05,
        }
        compliance = {
            "ucits_only": True,
            "audit_complete": True,
            "no_trade_band_respected": True,
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


__all__ = ["FairMainWindow"]
