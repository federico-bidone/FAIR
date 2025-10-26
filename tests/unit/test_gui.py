"""Tests for the optional PySide6 GUI orchestration layer."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np
import pytest

if "reportlab" not in sys.modules:
    reportlab_module = ModuleType("reportlab")
    reportlab_lib = ModuleType("reportlab.lib")
    reportlab_pagesizes = ModuleType("reportlab.lib.pagesizes")
    reportlab_pagesizes.A4 = (595.0, 842.0)

    reportlab_utils = ModuleType("reportlab.lib.utils")

    def _image_reader(path: str) -> str:
        return path

    reportlab_utils.ImageReader = _image_reader

    reportlab_pdfgen = ModuleType("reportlab.pdfgen")
    reportlab_canvas_mod = ModuleType("reportlab.pdfgen.canvas")

    class _DummyCanvas:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        def setFont(
            self, *args: object, **kwargs: object
        ) -> None:  # noqa: N802 - match reportlab API
            return None

        def drawString(
            self, *args: object, **kwargs: object
        ) -> None:  # noqa: N802 - match reportlab API
            return None

        def showPage(self) -> None:  # noqa: N802 - match reportlab API
            return None

        def drawImage(
            self, *args: object, **kwargs: object
        ) -> None:  # noqa: N802 - match reportlab API
            return None

        def save(self) -> None:
            return None

    reportlab_canvas_mod.Canvas = _DummyCanvas
    reportlab_pdfgen.canvas = reportlab_canvas_mod
    reportlab_module.lib = reportlab_lib
    reportlab_module.pdfgen = reportlab_pdfgen
    reportlab_lib.pagesizes = reportlab_pagesizes
    reportlab_lib.utils = reportlab_utils

    sys.modules.setdefault("reportlab", reportlab_module)
    sys.modules.setdefault("reportlab.lib", reportlab_lib)
    sys.modules.setdefault("reportlab.lib.pagesizes", reportlab_pagesizes)
    sys.modules.setdefault("reportlab.lib.utils", reportlab_utils)
    sys.modules.setdefault("reportlab.pdfgen", reportlab_pdfgen)
    sys.modules.setdefault("reportlab.pdfgen.canvas", reportlab_canvas_mod)

if "tqdm" not in sys.modules:
    tqdm_module = ModuleType("tqdm")
    tqdm_auto = ModuleType("tqdm.auto")

    def _tqdm(iterable: object | None = None, **kwargs: object) -> object:
        return iterable if iterable is not None else []

    tqdm_auto.tqdm = _tqdm
    tqdm_module.auto = tqdm_auto
    sys.modules.setdefault("tqdm", tqdm_module)
    sys.modules.setdefault("tqdm.auto", tqdm_auto)

if "hmmlearn" not in sys.modules:
    hmmlearn_module = ModuleType("hmmlearn")
    hmmlearn_hmm = ModuleType("hmmlearn.hmm")

    class _DummyGaussianHMM:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.means_ = np.array([[0.0], [1.0]], dtype=float)

        def fit(self, values: np.ndarray) -> _DummyGaussianHMM:
            self._n_obs = len(values)
            return self

        def predict_proba(self, values: np.ndarray) -> np.ndarray:
            count = len(values)
            probs = np.zeros((count, 2), dtype=float)
            probs[:, 0] = 0.6
            probs[:, 1] = 0.4
            return probs

        def predict(self, values: np.ndarray) -> np.ndarray:
            return np.zeros(len(values), dtype=int)

    hmmlearn_hmm.GaussianHMM = _DummyGaussianHMM
    hmmlearn_module.hmm = hmmlearn_hmm
    sys.modules.setdefault("hmmlearn", hmmlearn_module)
    sys.modules.setdefault("hmmlearn.hmm", hmmlearn_hmm)

import fair3.engine.gui as gui  # noqa: E402,I001


_LAST_WINDOWS: list[object] = []


class _DummySignal:
    """Minimal signal stub exposing a Qt-compatible connect API."""

    def __init__(self) -> None:
        self._callback: Callable[..., object] | None = None

    def connect(self, callback: Callable[..., object]) -> None:
        """Store the callback without invoking it."""

        self._callback = callback


class _DummyWidget:
    """Base widget that ignores positional and keyword arguments."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._layout = None

    def setLayout(self, layout: object) -> None:  # noqa: N802
        self._layout = layout

    def addTab(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def addWidget(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def addLayout(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def addRow(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def resize(self, *args: object, **kwargs: object) -> None:
        return None

    def setCentralWidget(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def setWindowTitle(self, *args: object, **kwargs: object) -> None:  # noqa: N802
        return None

    def show(self) -> None:
        return None


class _DummyPlainTextEdit(_DummyWidget):
    """Plain text edit widget that records appended messages."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.text: list[str] = []

    def setReadOnly(self, *_: object, **__: object) -> None:  # noqa: N802
        return None

    def appendPlainText(self, value: str) -> None:  # noqa: N802
        self.text.append(value)


class _DummyComboBox(_DummyWidget):
    """Combo box storing the provided options for inspection."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._items: list[str] = []
        self._index = 0

    def addItems(self, items: list[str]) -> None:  # noqa: N802
        self._items.extend(items)

    def currentText(self) -> str:  # noqa: N802
        if not self._items:
            return ""
        return self._items[self._index]


class _DummyLineEdit(_DummyWidget):
    """Line edit recording the entered text value."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._text = ""

    def setPlaceholderText(self, *_: object, **__: object) -> None:  # noqa: N802
        return None

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:  # noqa: D401 - short getter description
        """Return the stored string value."""

        return self._text


class _DummyPushButton(_DummyWidget):
    """Push button exposing a dummy clicked signal."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.clicked = _DummySignal()


class _DummyLayout(_DummyWidget):
    """Layout placeholder that ignores all operations."""


class _DummyApplication:
    """Application stub returning immediately on exec()."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        return None

    def exec(self) -> int:
        return 0


class _DummyMainWindow(_DummyWidget):
    """Main window stub inheriting behaviour from the generic widget."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        _LAST_WINDOWS.append(self)


def _install_qt_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject PySide6.QtWidgets stubs into sys.modules."""

    qtwidgets = ModuleType("PySide6.QtWidgets")
    qtwidgets.QApplication = _DummyApplication
    qtwidgets.QMainWindow = _DummyMainWindow
    qtwidgets.QWidget = _DummyWidget
    qtwidgets.QPlainTextEdit = _DummyPlainTextEdit
    qtwidgets.QTabWidget = _DummyWidget
    qtwidgets.QVBoxLayout = _DummyLayout
    qtwidgets.QFormLayout = _DummyLayout
    qtwidgets.QGridLayout = _DummyLayout
    qtwidgets.QComboBox = _DummyComboBox
    qtwidgets.QLineEdit = _DummyLineEdit
    qtwidgets.QPushButton = _DummyPushButton

    root = ModuleType("PySide6")
    root.QtWidgets = qtwidgets
    monkeypatch.setitem(sys.modules, "PySide6", root)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)


def _last_message(window: object) -> str:
    """Return the latest log message without the timestamp prefix."""

    if not window._log_output.text:  # pragma: no cover - defensive guard
        return ""
    raw = window._log_output.text[-1]
    if "] " in raw:
        return raw.split("] ", 1)[1]
    return raw


@pytest.fixture()
def gui_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, object]:
    """Create a GUI window with stubbed dependencies for interaction tests."""

    _install_qt_stubs(monkeypatch)
    _LAST_WINDOWS.clear()

    context: dict[str, object] = {}

    monkeypatch.setattr(gui, "available_sources", lambda: ("stub_source",))

    ingest_calls: list[dict[str, object]] = []

    def _run_ingest(
        source: str,
        *,
        symbols: tuple[str, ...] | None,
        start: date | None,
        raw_root: Path | None,
    ) -> SimpleNamespace:
        ingest_calls.append(
            {
                "source": source,
                "symbols": symbols,
                "start": start,
                "raw_root": raw_root,
            }
        )
        return SimpleNamespace(source=source, data=[1, 2], path=Path("ingest.csv"))

    monkeypatch.setattr(gui, "run_ingest", _run_ingest)
    context["ingest_calls"] = ingest_calls

    builder_calls: list[dict[str, object]] = []

    class _Builder:
        def __init__(self, **kwargs: object) -> None:
            builder_calls.append({"init": kwargs})

        def build(
            self, *, seed: int, trace: bool
        ) -> SimpleNamespace:  # noqa: D401 - interface parity
            builder_calls[-1]["build"] = {"seed": seed, "trace": trace}
            return SimpleNamespace(
                prices_path=Path("prices.parquet"),
                returns_path=Path("returns.parquet"),
            )

    monkeypatch.setattr(gui, "TRPanelBuilder", _Builder)
    context["builder_calls"] = builder_calls

    factor_calls: list[dict[str, object]] = []

    def _run_factors(**kwargs: object) -> SimpleNamespace:
        factor_calls.append(kwargs)
        return SimpleNamespace(factors_path=Path("factors.parquet"))

    monkeypatch.setattr(gui, "run_factor_pipeline", _run_factors)
    context["factor_calls"] = factor_calls

    estimate_calls: list[dict[str, object]] = []

    def _run_estimate(**kwargs: object) -> SimpleNamespace:
        estimate_calls.append(kwargs)
        return SimpleNamespace(mu_path=Path("mu.parquet"), sigma_path=Path("sigma.parquet"))

    monkeypatch.setattr(gui, "run_estimate_pipeline", _run_estimate)
    context["estimate_calls"] = estimate_calls

    mapping_calls: list[dict[str, object]] = []

    def _run_mapping(**kwargs: object) -> SimpleNamespace:
        mapping_calls.append(kwargs)
        return SimpleNamespace(
            instrument_weights_path=Path("instrument.csv"),
            factor_weights_path=Path("factor.csv"),
        )

    monkeypatch.setattr(gui, "run_mapping_pipeline", _run_mapping)
    context["mapping_calls"] = mapping_calls

    regime_calls: list[dict[str, object]] = []

    def _run_regime(**kwargs: object) -> SimpleNamespace:
        regime_calls.append(kwargs)
        return SimpleNamespace(probabilities_path=Path("regime.csv"))

    monkeypatch.setattr(gui, "run_regime_pipeline", _run_regime)
    context["regime_calls"] = regime_calls

    goal_calls: list[dict[str, object]] = []
    goal_summary = SimpleNamespace(weighted_probability=0.75)
    goal_artifacts = SimpleNamespace(report_pdf=Path("reports/goals/report.pdf"))

    def _load_goal_configs(_: Path) -> list[str]:
        return ["goal"]

    def _load_goal_params(_: Path) -> SimpleNamespace:
        return SimpleNamespace()

    def _run_goal_mc(
        goals: list[str],
        *,
        draws: int,
        seed: int,
        parameters: SimpleNamespace,
        output_dir: Path | None,
    ) -> tuple[SimpleNamespace, SimpleNamespace]:
        goal_calls.append(
            {
                "goals": goals,
                "draws": draws,
                "seed": seed,
                "parameters": parameters,
                "output_dir": output_dir,
            }
        )
        return goal_summary, goal_artifacts

    monkeypatch.setattr(gui, "load_goal_configs_from_yaml", _load_goal_configs)
    monkeypatch.setattr(gui, "load_goal_parameters", _load_goal_params)
    monkeypatch.setattr(gui, "run_goal_monte_carlo", _run_goal_mc)

    context["goal_calls"] = goal_calls
    context["goal_results"] = (goal_summary, goal_artifacts)

    opened_urls: list[str] = []

    def _open(url: str) -> bool:
        opened_urls.append(url)
        return True

    monkeypatch.setattr(gui.webbrowser, "open", _open)
    context["opened_urls"] = opened_urls

    gui.launch_gui({"report_path": tmp_path / "report.pdf"})
    assert _LAST_WINDOWS, "GUI did not create a main window"
    window = _LAST_WINDOWS.pop()
    window._log_output.text.clear()
    context["window"] = window
    return context


def test_launch_gui_missing_dependency(caplog: pytest.LogCaptureFixture) -> None:
    """The GUI returns immediately when PySide6 is not installed."""

    sys.modules.pop("PySide6", None)
    caplog.set_level("INFO")
    gui.launch_gui({})
    assert any("PySide6 not installed" in record.message for record in caplog.records)


def test_launch_gui_smoke_with_stubs(gui_env: dict[str, object]) -> None:
    """A stubbed PySide6 environment allows the GUI to initialise."""

    window = gui_env["window"]
    assert window._source_combo.currentText() == "stub_source"
    assert not window._log_output.text


def test_run_ingest_success(gui_env: dict[str, object]) -> None:
    """Running ingest logs the artifact path and records the call."""

    window = gui_env["window"]
    window._symbols_edit.setText("AAA, BBB")
    window._start_edit.setText("2020-01-02")
    window._run_ingest()

    calls = gui_env["ingest_calls"]
    assert len(calls) == 1
    call = calls[0]
    assert call["source"] == "stub_source"
    assert call["symbols"] == ("AAA", "BBB")
    assert call["start"] == date(2020, 1, 2)
    assert call["raw_root"] is None
    assert _last_message(window).startswith("Ingest complete")


def test_run_ingest_invalid_start(gui_env: dict[str, object]) -> None:
    """Invalid start dates prevent ingest execution and surface guidance."""

    window = gui_env["window"]
    window._start_edit.setText("invalid-date")
    window._run_ingest()
    assert not gui_env["ingest_calls"]
    assert _last_message(window) == "Invalid start date format; expected YYYY-MM-DD"


def test_run_ingest_failure(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors raised by run_ingest are captured and logged."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network down")

    monkeypatch.setattr(gui, "run_ingest", _boom)
    window = gui_env["window"]
    window._run_ingest()
    assert not gui_env["ingest_calls"]
    assert "Ingest failed" in _last_message(window)


def test_run_etl_success(gui_env: dict[str, object]) -> None:
    """The ETL helper builds panels and records builder usage."""

    window = gui_env["window"]
    window._run_etl()
    calls = gui_env["builder_calls"]
    assert len(calls) == 1
    init_args = calls[0]["init"]
    assert init_args["raw_root"] == Path("data/raw")
    assert init_args["clean_root"] == Path("data/clean")
    assert init_args["audit_root"] == Path("audit")
    assert init_args["base_currency"] == "EUR"
    assert calls[0]["build"] == {"seed": 0, "trace": False}
    assert "ETL complete" in _last_message(window)


def test_run_etl_failure(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Builder failures are surfaced to the GUI log."""

    class _ExplodingBuilder:
        def __init__(self, **_: object) -> None:
            return None

        def build(self, *, seed: int, trace: bool) -> None:  # noqa: D401 - interface parity
            raise RuntimeError(f"boom {seed} {trace}")

    monkeypatch.setattr(gui, "TRPanelBuilder", _ExplodingBuilder)
    window = gui_env["window"]
    window._run_etl()
    assert "ETL failed" in _last_message(window)


def test_run_factors_success(gui_env: dict[str, object]) -> None:
    """The factor pipeline is invoked with default paths."""

    window = gui_env["window"]
    window._run_factors()
    calls = gui_env["factor_calls"]
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["clean_root"] == "data/clean"
    assert kwargs["artifacts_root"] is None
    assert kwargs["audit_dir"] is None
    assert kwargs["seed"] == 0
    assert "Factors complete" in _last_message(window)


def test_run_factors_failure(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Exceptions from the factor pipeline are logged."""

    def _boom(**_: object) -> None:
        raise ValueError("bad factors")

    monkeypatch.setattr(gui, "run_factor_pipeline", _boom)
    window = gui_env["window"]
    window._run_factors()
    assert "Factor pipeline failed" in _last_message(window)


def test_run_estimate_success(gui_env: dict[str, object]) -> None:
    """The estimate pipeline wires thresholds and sigma engine options."""

    window = gui_env["window"]
    window._run_estimate()
    calls = gui_env["estimate_calls"]
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["thresholds"] == Path("configs/thresholds.yml")
    assert kwargs["sigma_engine"] == "median_psd"
    assert kwargs["seed"] == 0
    assert "Estimate complete" in _last_message(window)


def test_run_estimate_failure(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Failures in the estimate pipeline are propagated to the log widget."""

    def _boom(**_: object) -> None:
        raise RuntimeError("estimate failure")

    monkeypatch.setattr(gui, "run_estimate_pipeline", _boom)
    window = gui_env["window"]
    window._run_estimate()
    assert "Estimate pipeline failed" in _last_message(window)


def test_run_mapping_success(gui_env: dict[str, object]) -> None:
    """Mapping completes with deterministic defaults."""

    window = gui_env["window"]
    window._run_mapping()
    calls = gui_env["mapping_calls"]
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["thresholds"] == Path("configs/thresholds.yml")
    assert kwargs["seed"] == 0
    assert kwargs["bootstrap"] == 200
    assert "Mapping complete" in _last_message(window)


def test_run_mapping_failure(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Mapping errors are captured."""

    def _boom(**_: object) -> None:
        raise RuntimeError("mapping failed")

    monkeypatch.setattr(gui, "run_mapping_pipeline", _boom)
    window = gui_env["window"]
    window._run_mapping()
    assert "Mapping pipeline failed" in _last_message(window)


def test_run_regime_success(gui_env: dict[str, object]) -> None:
    """Regime pipeline outputs are acknowledged."""

    window = gui_env["window"]
    window._run_regime()
    calls = gui_env["regime_calls"]
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["thresholds"] == Path("configs/thresholds.yml")
    assert kwargs["seed"] == 0
    assert "Regime complete" in _last_message(window)


def test_run_regime_failure(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Regime errors are logged for operator follow-up."""

    def _boom(**_: object) -> None:
        raise RuntimeError("regime failure")

    monkeypatch.setattr(gui, "run_regime_pipeline", _boom)
    window = gui_env["window"]
    window._run_regime()
    assert "Regime pipeline failed" in _last_message(window)


def test_run_goals_success(gui_env: dict[str, object]) -> None:
    """Goal simulations use defaults and log weighted probability."""

    window = gui_env["window"]
    window._run_goals()
    calls = gui_env["goal_calls"]
    assert len(calls) == 1
    kwargs = calls[0]
    assert kwargs["draws"] == 10_000
    assert kwargs["seed"] == 0
    assert "Goals complete" in _last_message(window)


def test_run_goals_no_config(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty goal configuration produces a helpful log entry."""

    monkeypatch.setattr(gui, "load_goal_configs_from_yaml", lambda _path: [])
    window = gui_env["window"]
    window._run_goals()
    assert "Goals simulation failed" in _last_message(window)


def test_run_goals_failure(gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Errors surfaced by goal helper functions are logged."""

    def _boom(_path: Path) -> None:
        raise FileNotFoundError("missing params")

    monkeypatch.setattr(gui, "load_goal_parameters", _boom)
    window = gui_env["window"]
    window._run_goals()
    assert "Goals simulation failed" in _last_message(window)


def test_open_report_empty(gui_env: dict[str, object]) -> None:
    """Empty paths request user input instead of opening the browser."""

    window = gui_env["window"]
    window._report_path_edit.setText("")
    window._open_report()
    assert not gui_env["opened_urls"]
    assert _last_message(window) == "Provide a report path to open"


def test_open_report_missing(gui_env: dict[str, object], tmp_path: Path) -> None:
    """Non-existing report paths do not invoke the browser."""

    window = gui_env["window"]
    window._report_path_edit.setText(str(tmp_path / "missing.pdf"))
    window._open_report()
    assert not gui_env["opened_urls"]
    assert "Report not found" in _last_message(window)


def test_open_report_failure(
    gui_env: dict[str, object], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Browser errors are captured in the log for the operator."""

    def _boom(url: str) -> bool:
        raise OSError(f"cannot open {url}")

    monkeypatch.setattr(gui.webbrowser, "open", _boom)
    window = gui_env["window"]
    report = tmp_path / "fake.pdf"
    report.write_bytes(b"")
    window._report_path_edit.setText(str(report))
    window._open_report()
    assert "Unable to open report" in _last_message(window)


def test_open_report_success(gui_env: dict[str, object], tmp_path: Path) -> None:
    """Valid report paths trigger the browser helper."""

    window = gui_env["window"]
    report = tmp_path / "report.pdf"
    report.write_bytes(b"%PDF")
    window._report_path_edit.setText(str(report))
    window._open_report()
    assert gui_env["opened_urls"]
    assert "Opening report" in _last_message(window)
