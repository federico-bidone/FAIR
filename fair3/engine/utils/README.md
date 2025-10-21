# Utils Module

The utilities package centralises shared concerns such as deterministic randomness, structured
logging, and artifact management. These helpers keep higher-level engine modules focused on
quantitative logic while guaranteeing reproducibility and auditability demanded by FAIR-III.

## Public API

### Logging (`fair3.engine.utils.log`)
- `setup_logger(name, level="INFO", log_dir=None, max_bytes=1_048_576, backup_count=5, console=False)`
- `get_logger(name)`
- `default_log_dir()`

All log files rotate automatically under `artifacts/audit/`. Use `console=True` for verbose CLI
runs and `level="DEBUG"` when invoking `--trace` flags.

### Randomness (`fair3.engine.utils.rand`)
- `load_seeds(seed_path="audit/seeds.yml")`
- `save_seeds(seeds, seed_path="audit/seeds.yml")`
- `seed_for_stream(stream="global", seeds=None, seed_path=...)`
- `generator_from_seed(seed=None, stream="global", seeds=None, seed_path=...)`
- `broadcast_seed(seed)`
- `spawn_child_rng(parent, jumps=1)`

Streams fall back to the global seed and default to 42 when no file is present. The helpers seed
both NumPy and the Python standard library, ensuring consistent behaviour across workers.

### IO (`fair3.engine.utils.io`)
- `artifact_path(*parts, create=True, root=None)`
- `ensure_dir(path)`
- `read_yaml(path)` / `write_yaml(data, path)`
- `write_json(data, path, indent=2)`
- `sha256_file(path)` / `compute_checksums(paths)`
- `copy_with_timestamp(src, dest_dir, prefix=None, timestamp=None)`

Use `artifact_path` to resolve canonical output locations (e.g. `artifact_path("audit", "checksums.json")`).
Checksums stream large files safely using 64 KiB chunks.

### PSD (`fair3.engine.utils.psd`)
- `project_to_psd(matrix, eps=None)`

Projects symmetric matrici sul cono PSD usando la procedura di Higham (2002) con
`eps` calcolato automaticamente quando omesso.

## Examples

```python
from fair3.engine.utils import generator_from_seed, project_to_psd, setup_logger, artifact_path

rng = generator_from_seed(stream="factors")
logger = setup_logger("fair3.factors", level="DEBUG", console=True)
outfile = artifact_path("factors", "loadings.parquet")
logger.info("Saving factors to %s", outfile)
psd_cov = project_to_psd(covariance_matrix)
```

## Common Errors

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| `TypeError: Seed file must contain a mapping` | malformed `audit/seeds.yml` | Ensure YAML contains `seeds:` with key/value pairs |
| `FileNotFoundError` from `copy_with_timestamp` | source path missing | Run upstream pipeline step or adjust path |
| Duplicate log lines | logger propagation enabled twice | Set `propagate=False` (default) or remove parent handlers |

## Tracing and Debug Flags

The CLI will pass `--trace` to trigger `setup_logger(..., level="DEBUG", console=True)`. For
module-level debugging, request stream-specific RNGs (`generator_from_seed(stream="module"))`
and include the stream name in audit metadata.
