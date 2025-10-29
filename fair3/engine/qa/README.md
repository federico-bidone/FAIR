# QA pipeline module

> Strumento informativo/educational; non costituisce consulenza finanziaria o raccomandazione.

The QA engine fabricates a deterministic synthetic dataset, executes the entire
FAIR-III pipeline, and emits audit artefacts that confirm acceptance and
robustness gates.  It is the reference workflow for validating installations and
for debugging end-to-end regressions without hitting external data providers.

## Key components
- `DemoQAConfig`: immutable configuration for the QA scenario (calendar, label,
  bootstrap controls, acceptance thresholds, and seed stream).
- `DemoQAResult`: collection of output paths and pass/fail flags surfaced by the
  CLI handler.
- `run_demo_qa`: orchestrates ingest scaffolding, ETL, factors, estimates,
  optimisation, mapping, regime overlay, reporting, and robustness lab on the
  synthetic dataset.

## Usage
```bash
fair3 qa --label demo --draws 256 --block-size 45 --validate-factors
```

The command writes artefacts to `artifacts/qa/<label>/` by default.  Override the
location with `--output-dir` to keep QA runs isolated from production artefacts.
All outputs include checksum metadata so they can be diffed between releases.
