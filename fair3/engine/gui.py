"""Optional PySide6 GUI entrypoint for FAIR-III orchestration.

Provides a thin orchestration layer to trigger ingest and pipeline stages, view
log messages, and open generated reports. The GUI is intentionally lightweight
and falls back to a no-op when PySide6 is not installed.
"""

from __future__ import annotations

import logging
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from fair3.engine.estimates import run_estimate_pipeline
from fair3.engine.etl import TRPanelBuilder
from fair3.engine.factors import run_factor_pipeline
from fair3.engine.goals import (
    load_goal_configs_from_yaml,
    load_goal_parameters,
    run_goal_monte_carlo,
)
from fair3.engine.ingest import available_sources, run_ingest
from fair3.engine.mapping import run_mapping_pipeline
from fair3.engine.regime import run_regime_pipeline

LOG = logging.getLogger(__name__)


def launch_gui(cfg: dict[str, Any] | None = None) -> None:
    """Launch the optional PySide6 GUI.

    Args:
        cfg: Optional configuration dictionary with overrides for paths and defaults.

    Returns:
        None. The function returns when the GUI exits or when PySide6 is unavailable.

    Raises:
        RuntimeError: If the GUI fails to start despite PySide6 being installed.
    """

    configuration: dict[str, Any] = cfg.copy() if cfg else {}
    try:
        from PySide6 import QtWidgets
    except ImportError as exc:
        LOG.info("PySide6 not installed; skipping GUI launch: %s", exc)
        return

    class FairMainWindow(QtWidgets.QMainWindow):
        """Minimal orchestration window for FAIR-III workflows.

        Attributes:
            _options: Configuration overrides propagated from the caller.
            _log_output: Text area used to surface execution logs to the user.
            _source_combo: Combo box listing available ingest sources.
            _symbols_edit: Line edit for comma-separated symbols.
            _start_edit: Line edit for optional ingest start date.
            _report_path_edit: Line edit storing the report path to open.
        """

        def __init__(self, options: dict[str, Any]) -> None:
            """Initialise the main window and compose the UI elements.

            Args:
                options: Configuration overrides passed to the GUI.

            Returns:
                None.

            Raises:
                ValueError: If invalid options are provided (propagated implicitly).
            """
            super().__init__()
            self._options = options
            self.setWindowTitle("FAIR-III Orchestrator")
            self.resize(960, 640)

            self._log_output = QtWidgets.QPlainTextEdit(self)
            self._log_output.setReadOnly(True)

            tabs = QtWidgets.QTabWidget(self)
            tabs.addTab(self._build_ingest_tab(), "Ingest")
            tabs.addTab(self._build_pipeline_tab(), "Pipeline")
            tabs.addTab(self._build_reports_tab(), "Reports")

            container = QtWidgets.QWidget(self)
            layout = QtWidgets.QVBoxLayout(container)
            layout.addWidget(tabs)
            layout.addWidget(self._log_output)
            container.setLayout(layout)
            self.setCentralWidget(container)

        def _append_log(self, message: str) -> None:
            """Append a timestamped message to the log text area.

            Args:
                message: Text to append to the GUI log widget.

            Returns:
                None.
            """
            timestamp = datetime.now().isoformat(timespec="seconds")
            self._log_output.appendPlainText(f"[{timestamp}] {message}")

        def _build_ingest_tab(self) -> QtWidgets.QWidget:
            """Create the ingest tab with source and date controls.

            Returns:
                Widget containing ingest controls.
            """
            widget = QtWidgets.QWidget(self)
            layout = QtWidgets.QFormLayout(widget)

            self._source_combo = QtWidgets.QComboBox(widget)
            self._source_combo.addItems(sorted(available_sources()))

            self._symbols_edit = QtWidgets.QLineEdit(widget)
            self._symbols_edit.setPlaceholderText("Symbol1,Symbol2 (optional)")

            self._start_edit = QtWidgets.QLineEdit(widget)
            self._start_edit.setPlaceholderText("YYYY-MM-DD")

            run_button = QtWidgets.QPushButton("Run Ingest", widget)
            run_button.clicked.connect(self._run_ingest)

            layout.addRow("Source", self._source_combo)
            layout.addRow("Symbols", self._symbols_edit)
            layout.addRow("Start date", self._start_edit)
            layout.addRow(run_button)
            widget.setLayout(layout)
            return widget

        def _build_pipeline_tab(self) -> QtWidgets.QWidget:
            """Create the pipeline tab with buttons for each stage.

            Returns:
                Widget containing pipeline shortcuts.
            """
            widget = QtWidgets.QWidget(self)
            layout = QtWidgets.QVBoxLayout(widget)

            pipeline_buttons = QtWidgets.QGridLayout()

            etl_button = QtWidgets.QPushButton("Run ETL", widget)
            etl_button.clicked.connect(self._run_etl)
            pipeline_buttons.addWidget(etl_button, 0, 0)

            factors_button = QtWidgets.QPushButton("Run Factors", widget)
            factors_button.clicked.connect(self._run_factors)
            pipeline_buttons.addWidget(factors_button, 0, 1)

            estimate_button = QtWidgets.QPushButton("Run Estimate", widget)
            estimate_button.clicked.connect(self._run_estimate)
            pipeline_buttons.addWidget(estimate_button, 1, 0)

            mapping_button = QtWidgets.QPushButton("Run Mapping", widget)
            mapping_button.clicked.connect(self._run_mapping)
            pipeline_buttons.addWidget(mapping_button, 1, 1)

            regime_button = QtWidgets.QPushButton("Run Regime", widget)
            regime_button.clicked.connect(self._run_regime)
            pipeline_buttons.addWidget(regime_button, 2, 0)

            goals_button = QtWidgets.QPushButton("Run Goals", widget)
            goals_button.clicked.connect(self._run_goals)
            pipeline_buttons.addWidget(goals_button, 2, 1)

            layout.addLayout(pipeline_buttons)
            widget.setLayout(layout)
            return widget

        def _build_reports_tab(self) -> QtWidgets.QWidget:
            """Create the reports tab with controls to open PDFs.

            Returns:
                Widget containing report utilities.
            """
            widget = QtWidgets.QWidget(self)
            layout = QtWidgets.QVBoxLayout(widget)

            self._report_path_edit = QtWidgets.QLineEdit(widget)
            report_default = self._options.get("report_path")
            if report_default:
                self._report_path_edit.setText(str(report_default))
            self._report_path_edit.setPlaceholderText("Path to report PDF")

            open_button = QtWidgets.QPushButton("Open Report", widget)
            open_button.clicked.connect(self._open_report)

            layout.addWidget(self._report_path_edit)
            layout.addWidget(open_button)
            widget.setLayout(layout)
            return widget

        def _run_ingest(self) -> None:
            """Execute the ingest workflow for the selected source.

            Returns:
                None.
            """
            source = self._source_combo.currentText()
            symbols_text = self._symbols_edit.text().strip()
            symbol_list = [sym.strip() for sym in symbols_text.split(",") if sym.strip()]
            start_text = self._start_edit.text().strip()
            start_date = None
            if start_text:
                try:
                    start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
                except ValueError:
                    self._append_log("Invalid start date format; expected YYYY-MM-DD")
                    return
            try:
                artifact = run_ingest(
                    source,
                    symbols=tuple(symbol_list) or None,
                    start=start_date,
                    raw_root=self._options.get("raw_root"),
                )
            except Exception as exc:  # noqa: BLE001 - surfaced to GUI
                self._append_log(f"Ingest failed: {exc}")
            else:
                self._append_log(
                    f"Ingest complete for {artifact.source} "
                    f"({len(artifact.data)} rows) -> {artifact.path}"
                )

        def _run_etl(self) -> None:
            """Execute the ETL workflow using configured paths.

            Returns:
                None.
            """
            raw_root = Path(self._options.get("raw_root", "data/raw"))
            clean_root = Path(self._options.get("clean_root", "data/clean"))
            audit_root = Path(self._options.get("audit_root", "audit"))
            builder = TRPanelBuilder(
                raw_root=raw_root,
                clean_root=clean_root,
                audit_root=audit_root,
                base_currency=self._options.get("base_currency", "EUR"),
            )
            try:
                artifacts = builder.build(seed=int(self._options.get("seed", 0)), trace=False)
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"ETL failed: {exc}")
            else:
                self._append_log(
                    f"ETL complete: panel={artifacts.panel_path} checksum={artifacts.checksum}"
                )

        def _run_factors(self) -> None:
            """Execute the factor pipeline with default thresholds.

            Returns:
                None.
            """
            try:
                result = run_factor_pipeline(
                    clean_root=self._options.get("clean_root", "data/clean"),
                    artifacts_root=self._options.get("artifacts_root"),
                    audit_dir=self._options.get("audit_root"),
                    seed=int(self._options.get("seed", 0)),
                )
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"Factor pipeline failed: {exc}")
            else:
                self._append_log(f"Factors complete: {result.factors_path}")

        def _run_estimate(self) -> None:
            """Execute the estimation pipeline with configured sigma engine.

            Returns:
                None.
            """
            try:
                result = run_estimate_pipeline(
                    artifacts_root=self._options.get("artifacts_root"),
                    audit_dir=self._options.get("audit_root"),
                    thresholds=Path(self._options.get("thresholds", "configs/thresholds.yml")),
                    sigma_engine=self._options.get("sigma_engine", "median_psd"),
                    seed=int(self._options.get("seed", 0)),
                )
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"Estimate pipeline failed: {exc}")
            else:
                self._append_log(
                    f"Estimate complete: mu={result.mu_path} sigma={result.sigma_path}"
                )

        def _run_mapping(self) -> None:
            """Execute the mapping pipeline to produce allocations.

            Returns:
                None.
            """
            try:
                result = run_mapping_pipeline(
                    clean_root=self._options.get("clean_root", "data/clean"),
                    artifacts_root=self._options.get("artifacts_root"),
                    audit_dir=self._options.get("audit_root"),
                    thresholds=Path(self._options.get("thresholds", "configs/thresholds.yml")),
                    seed=int(self._options.get("seed", 0)),
                    bootstrap=int(self._options.get("bootstrap", 200)),
                )
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"Mapping pipeline failed: {exc}")
            else:
                self._append_log(
                    "Mapping complete: instruments="
                    f"{result.instrument_weights_path} factors={result.factor_weights_path}"
                )

        def _run_regime(self) -> None:
            """Execute the regime pipeline and persist outputs.

            Returns:
                None.
            """
            try:
                result = run_regime_pipeline(
                    clean_root=self._options.get("clean_root", "data/clean"),
                    thresholds=Path(self._options.get("thresholds", "configs/thresholds.yml")),
                    seed=int(self._options.get("seed", 0)),
                    output_dir=self._options.get("regime_dir"),
                )
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"Regime pipeline failed: {exc}")
            else:
                self._append_log(f"Regime complete: probabilities={result.probabilities_path}")

        def _run_goals(self) -> None:
            """Execute the regime-aware goal Monte Carlo simulation.

            Returns:
                None.
            """
            try:
                goals = load_goal_configs_from_yaml(
                    Path(self._options.get("goals", "configs/goals.yml"))
                )
                if not goals:
                    raise ValueError("No goals configured")
                params = load_goal_parameters(
                    Path(self._options.get("params", "configs/params.yml"))
                )
                draws = int(self._options.get("goal_draws", 10_000))
                summary, artifacts = run_goal_monte_carlo(
                    goals,
                    draws=draws,
                    seed=int(self._options.get("seed", 0)),
                    parameters=params,
                    output_dir=self._options.get("goals_dir"),
                )
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"Goals simulation failed: {exc}")
            else:
                self._append_log(
                    f"Goals complete: weighted={summary.weighted_probability:.3f} "
                    f"pdf={artifacts.report_pdf}"
                )

        def _open_report(self) -> None:
            """Open the user-provided report path in the system browser.

            Returns:
                None.
            """
            path_text = self._report_path_edit.text().strip()
            if not path_text:
                self._append_log("Provide a report path to open")
                return
            path = Path(path_text)
            if not path.exists():
                self._append_log(f"Report not found: {path}")
                return
            try:
                webbrowser.open(path.resolve().as_uri())
            except Exception as exc:  # noqa: BLE001
                self._append_log(f"Unable to open report: {exc}")
            else:
                self._append_log(f"Opening report {path}")

    app = QtWidgets.QApplication(sys.argv or ["fair3-gui"])
    window = FairMainWindow(configuration)
    window.show()
    exit_code = app.exec()
    if exit_code != 0:
        raise RuntimeError(f"GUI exited with non-zero status {exit_code}")
