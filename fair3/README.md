# fair3 package overview

> Strumento informativo/educational; non costituisce consulenza finanziaria o raccomandazione.

The `fair3` package implements the FAIR-III portfolio research stack.  Every
module respects the Google Python Style Guide, exposes typed, reusable
entrypoints, and is callable both via CLI wiring and from downstream Python
code.

## Layout
- `fair3/cli/`: argparse-based command registration with deterministic defaults
  and audit-friendly logging.
- `fair3/engine/`: domain engines covering ingest, ETL, factor construction,
  estimates, optimisation, mapping, regime detection, execution, reporting, QA,
  robustness, and utilities.
- `fair3/configs/`: runtime configuration loaders (not yet part of the public
  API in v0.2).

## Contributor notes
- Follow the PyGuide docstring structure (`Args`, `Returns`, `Raises`,
  `Attributes`) and keep imports grouped (stdlib, third-party, local).
- Prefer deterministic helpers that accept explicit seeds sourced from
  `audit/seeds.yml`.
- Log license metadata, checksums, and paths whenever new artefacts are
  produced so that the QA pipeline can surface discrepancies immediately.
