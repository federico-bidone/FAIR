# `fair3.engine.utils`

## Panoramica (Italiano)
La directory contiene gli strumenti trasversali che supportano le pipeline FAIR-III.
Gli obiettivi principali sono:

- fornire utilità di logging condivise e verbose per tutta la piattaforma tramite
  il modulo `fair3.engine.logging`;
- gestire input/output di configurazioni, artefatti e checksum in modo riproducibile;
- mantenere generatori casuali deterministici e proiezioni matematiche sicure.

Ogni modulo espone docstring e commenti in italiano che spiegano cosa fa ogni
funzione, come lo fa e perché è utile nel flusso complessivo.

### Moduli principali

- **`logging`** – (spostato in `fair3.engine.logging`) fornisce logger strutturati
  con mirroring JSON, progress bar e helper per metriche; le docstring spiegano
  le variabili d'ambiente supportate e come ri-configurare i loggers dal CLI.
- **`io`** – gestisce cartelle di artefatti, serializzazioni YAML/JSON
  deterministiche e checksum; ogni funzione documenta il comportamento sui
  corner case (percorso inesistente, file corrotti, ecc.).
- **`rand`** – normalizza la gestione dei seed, documentando il formato del file
  `audit/seeds.yml` e la strategia per stream multipli; i test coprono
  conversioni di tipo e generazione di RNG figlio.
- **`psd`** – applica la proiezione di Higham con spiegazioni sulle soglie
  automatiche per la stabilità numerica.

---

## Utils Module (English Reference)

The utilities package centralises shared concerns such as deterministic randomness, structured
logging, and artifact management. These helpers keep higher-level engine modules focused on
quantitative logic while guaranteeing reproducibility and auditability demanded by FAIR-III.

### Public API

#### Logging (`fair3.engine.logging`)
- `setup_logger(name, json_format=False, level=None)`
- `record_metrics(metric_name, value, tags=None)`
- `configure_cli_logging(json_logs, level=None)`

Structured logs live in `artifacts/audit/fair3.log` when `json_format=True` or
`FAIR_JSON_LOGS=1`. Console output always follows `[LEVEL] module: message`. Metrics are appended
to `artifacts/audit/metrics.jsonl` for downstream observability.

#### Randomness (`fair3.engine.utils.rand`)
- `load_seeds(seed_path="audit/seeds.yml")`
- `save_seeds(seeds, seed_path="audit/seeds.yml")`
- `seed_for_stream(stream="global", seeds=None, seed_path=...)`
- `generator_from_seed(seed=None, stream="global", seeds=None, seed_path=...)`
- `broadcast_seed(seed)`
- `spawn_child_rng(parent, jumps=1)`

Streams fall back to the global seed and default to 42 when no file is present. The helpers seed
both NumPy and the Python standard library, ensuring consistent behaviour across workers.

#### IO (`fair3.engine.utils.io`)
- `artifact_path(*parts, create=True, root=None)`
- `ensure_dir(path)`
- `read_yaml(path)` / `write_yaml(data, path)`
- `write_json(data, path, indent=2)`
- `sha256_file(path)` / `compute_checksums(paths)`
- `copy_with_timestamp(src, dest_dir, prefix=None, timestamp=None)`

Use `artifact_path` to resolve canonical output locations (e.g. `artifact_path("audit", "checksums.json")`).
Checksums stream large files safely using 64 KiB chunks.

#### PSD (`fair3.engine.utils.psd`)
- `project_to_psd(matrix, eps=None)`

Projects symmetric matrici sul cono PSD usando la procedura di Higham (2002) con
`eps` calcolato automaticamente quando omesso.

## Examples

```python
from fair3.engine.logging import setup_logger
from fair3.engine.utils import generator_from_seed, project_to_psd, artifact_path

rng = generator_from_seed(stream="factors")
logger = setup_logger("fair3.factors", json_format=True)
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

The CLI exposes `--json-logs/--no-json-logs` to toggle the JSON audit mirror and honours
`FAIR_LOG_LEVEL=DEBUG` for verbose diagnostics. For module-level debugging, request
stream-specific RNGs (`generator_from_seed(stream="module"))` and include the stream name in
audit metadata.
