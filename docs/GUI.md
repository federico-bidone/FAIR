# FAIR-III GUI (PySide6)

"""Strumento informativo/educational; non costituisce consulenza finanziaria o raccomandazione."""

The optional PySide6 GUI provides a thin orchestration layer over the existing
CLI commands. It is intended for exploratory desktop workflows where a visual
control panel is preferable to shell invocations.

## Installation

Install PySide6 alongside the FAIR-III extras:

```bash
pip install PySide6
```

No other dependencies are required; the GUI relies entirely on the engines
already bundled in FAIR-III.

## Launching the GUI

Use the CLI wrapper to launch the interface:

```bash
fair3 gui --raw-root data/raw --clean-root data/clean --artifacts-root artifacts
```

The command accepts the same path overrides as the CLI to seed the interface.
Passing `--dry-run` prints the derived configuration without starting the GUI,
useful when validating configuration inside headless environments.

## Features

- **Ingest tab:** select any registered source, supply optional symbols and a
  start date, and trigger ingestion. Status lines mirror the CLI output and
  append to the log panel.
- **Pipeline tab:** buttons dispatch the ETL, factor, estimate, mapping, regime,
  and goal engines using the configured directories and thresholds.
- **Reports tab:** supply a PDF path to open with the platform default viewer.

All actions catch exceptions and record them in the on-screen log so the
application remains responsive even if a pipeline stage fails. When PySide6 is
not installed the GUI quietly skips execution after logging a hint.

## Troubleshooting

- **Missing PySide6:** install the package or rely on the CLI (`launch_gui`
  returns immediately and logs an info message).
- **Long-running tasks:** pipeline executions occur on the GUI thread and may
  block the window. For production runs prefer the CLI or wrap actions with
  background scheduling.

Remember that the GUI inherits all UCITS/EU/IT compliance constraints documented
in the README and does not change the deterministic behaviour of the pipelines.
