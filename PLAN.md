# PR-15 Plan

## Scope
- Orchestrate the factor → estimate → optimisation → mapping pipeline with audit-aware
  helpers and CLI wiring (`fair3 factors|estimate|optimize|map`).
- Emit deterministic artefacts for each stage (factors, μ/Σ, generator weights, instrument
  mapping) and ensure audit snapshots (seeds/configs/checksums) are captured.
- Refresh documentation (README + module READMEs + architecture/methodology notes) to
  describe the new orchestration workflow and artefact layout.

## Design Notes
- Introduce `run_factor_pipeline`, `run_estimate_pipeline`, `run_optimization_pipeline`,
  and `run_mapping_pipeline` returning dataclasses with artefact paths to keep CLI thin and
  testable.
- Ensure covariances remain PSD and drift diagnostics rely on consistent correlation
  matrices (Higham projection + safe correlation conversion).
- Maintain deterministic RNG streams via `utils.rand.DEFAULT_SEED_PATH`; tests monkeypatch
  the root to avoid polluting repository artefacts.

## Testing
- CLI regression test (`tests/unit/test_cli_pipeline.py`) covering the full synthetic flow
  from factors to instrument mapping.
- Full repository checks: `pytest -q`, `ruff check .`, `ruff format --check .`,
  `black --check .`.
