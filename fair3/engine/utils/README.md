# `fair3.engine.utils`

## Panoramica (Italiano)
La directory contiene gli strumenti trasversali che supportano le pipeline FAIR-III.
Gli obiettivi principali sono:

- fornire utilità di logging condiviso e verbose per tutta la piattaforma tramite
  il modulo `fair3.engine.logging`;
- gestire input/output di distribuzione, artefatti e checksum in modoriproducibile;
- mantenere generatori casuali deterministici e proiezioni matematiche sicure.

Ogni modulo espone docstring e in italiano che spiega cosa fa ogni
funzione, come lo fa e perché è utile nel flusso complessivo.

### Moduli principali

- **`logging`** – (spostato in `fair3.engine.logging`) fornisce logger strutturati
  con mirroring JSON, progress bar e helper per metriche; le docstring spiegano
  le variabili d'ambiente supportate e come ri-configurare i logger dalla CLI.
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

The utilities package centralizza preoccupazioni condivise come determinismo casuale, strutturato
registrazione e gestione degli artefatti. Questi helper mantengono i moduli del motore di livello superiore incentrati sulla logica quantitativa
garantendo al tempo stesso la riproducibilità e la verificabilità richieste da FAIR-III.

### API pubblica

#### Logging(`fair3.engine.logging`)
- `setup_logger(name, json_format=False, level=None)`
- `record_metrics(metric_name, value, tags=None)`
- `configure_cli_logging(json_logs, level=None)`

Log strutturati presenti in `artifacts/audit/fair3.log` quando `json_format=True` o
`FAIR_JSON_LOGS=1`.L'output della console segue sempre `[LEVEL] module: message`.Le metriche vengono aggiunte
a `artifacts/audit/metrics.jsonl` per l'osservabilità a valle.

#### Casualità(`fair3.engine.utils.rand`)
- `load_seeds(seed_path="audit/seeds.yml")`
- `save_seeds(seeds, seed_path="audit/seeds.yml")`
- `seed_for_stream(stream="global", seeds=None, seed_path=...)`
- `generator_from_seed(seed=None, stream="global", seeds=None, seed_path=...)`
- `broadcast_seed(seed)`
- `spawn_child_rng(parent, jumps=1)`

Gli stream ritornano al seed globale e diventano 42 per impostazione predefinita quando non è presente alcun file. Gli helper seminano
sia NumPy che la libreria standard Python, garantendo un comportamento coerente tra i lavoratori.

#### IO (`fair3.engine.utils.io`)
- `artifact_path(*parts, create=True, root=None)`
- `ensure_dir(path)`
- `read_yaml(path)` / `write_yaml(data, path)`
- `write_json(data, path, indent=2)`
- `sha256_file(path)` / `compute_checksums(paths)`
- `copy_with_timestamp(src, dest_dir, prefix=None, timestamp=None)`

Utilizza `artifact_path` per risolvere posizioni di output canoniche (ad esempio `artifact_path("audit", "checksums.json")`).
I checksum trasmettono file di grandi dimensioni in modo sicuro utilizzando blocchi da 64 KiB.

#### PSD(`fair3.engine.utils.psd`)
- `project_to_psd(matrix, eps=None)`

Projects symmetric matrici sul cono PSD utilizzando la procedura di Higham (2002) con
`eps` calcolato automaticamente quando omesso.

## Esempi

```python
from fair3.engine.logging import setup_logger
from fair3.engine.utils import generator_from_seed, project_to_psd, artifact_path

rng = generator_from_seed(stream="factors")
logger = setup_logger("fair3.factors", json_format=True)
outfile = artifact_path("factors", "loadings.parquet")
logger.info("Saving factors to %s", outfile)
psd_cov = project_to_psd(covariance_matrix)
```

## Errori comuni

| Sintomo | Probabile causa | Risoluzione |
| --- | --- | --- |
| `TypeError: Seed file must contain a mapping` | malformato `audit/seeds.yml` | Assicurati che YAML contenga `seeds:` con coppie chiave/valore |
| `FileNotFoundError` da `copy_with_timestamp` | percorso di origine mancante | Eseguire il passaggio della pipeline upstream o modificare il percorso |
| Righe di registro duplicate | propagazione del logger abilitata due volte | Imposta `propagate=False` (impostazione predefinita) o rimuovi gestori principali |

## Flag di tracciamento e debug

La CLI espone `--json-logs/--no-json-logs` per attivare/disattivare il mirroring di controllo JSON e rispetta
`FAIR_LOG_LEVEL=DEBUG` per la diagnostica dettagliata. Per il debug a livello di modulo, richiedi
RNG specifici del flusso (`generator_from_seed(stream="module"))` e includi il nome del flusso nei
metadati di controllo.
