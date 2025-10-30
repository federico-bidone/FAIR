# Architettura FAIR-III

Questa guida descrive il flusso semantico completo del motore FAIR-III in modo che un agente LLM possa orientarsi rapidamente nella pipeline ingest → etl → factors → allocators/mapping → regime → reporting. Ogni sezione elenca invarianti, contratti tra sottosistemi ed estensioni suggerite.

## Panoramica dei flussi

```text
CLI (fair3) ──► ingest ──► etl ──► factors ──► estimates ──► allocators ──► mapping ──► regime ──► execution ──► reporting
                           │                    │                               │             │
                           ├──────────────► qa   ├──────────────► robustness     └────► goals   └────► audit artefacts
```

- **Determinismo:** ogni comando CLI acquisisce e propaga `seed`, checksum e licenze tramite `audit/`.
- **Artefatti PIT:** `data/raw/<source>/` contiene CSV timestampati; `data/clean/asset_panel.parquet` è l'output principale ETL.
- **Config condivise:** `configs/*.yml` guida fattori, stime, mapping, obiettivi e reporting; ogni pipeline copia la configurazione nell'audit trail.
- **Accesso orchestrato:** `fair3/cli/main.py` media le CLI e inietta i parametri comuni (`--dry-run`, `--json-logs`, `--progress`).

## Ingest

- **Responsabilità:** scaricare dati macro/mercato da fonti gratuite o manuali. Ogni fetcher eredita `BaseCSVFetcher` e implementa `fetch()` ritornando `IngestArtifact`.
- **Output:** CSV normalizzati con colonne `date`, `value`, `symbol`, `currency` opzionale e log licenza in `audit/`.
- **Invarianti:**
  - Ogni fetcher dichiara `source_id` e URL/licenza per audit.
  - I test di rete sono marcati `@pytest.mark.network` e abilitati solo con `pytest --network`.
- **Estensioni:** per un nuovo feed creare `<source>.py`, registrarlo in `registry.py` e aggiornare `docs/COMPONENTS.md`.

## ETL

- **Responsabilità:** costruire pannelli point-in-time con colonne di prezzi, rendimenti e feature tecniche.
- **Artefatti:**
  - `TRPanelBuilder` produce `TRPanelArtifacts` con percorsi e checksum.
  - QA: `write_qa_log()` scrive CSV con licenze e anomaly score.
- **Invarianti:**
  - Calendario unificato generato da `build_calendar()`.
  - Conversioni FX centralizzate in `FXFrame` con valuta base `EUR` (override via CLI).
  - Ogni feature deve dichiarare il campo `field` e passare lo schema `ASSET_PANEL_SCHEMA`.
- **Estensioni:** aggiungere trasformazioni in `make_tr_panel.py` rispettando il pattern `_compute_*` e aggiornando la checklist QA.

## Factors & Estimates

- **Responsabilità:** calcolare fattori macro/mercato e validarli, quindi stimare μ/Σ.
- **Fattori:** `FactorLibrary` definisce la ricetta; `run_factor_pipeline()` coordina calcolo, orthogonality e QA.
- **Stime:** pipeline `fair3 estimate` combina engine Σ (Ledoit–Wolf, SPD mediana, etc.) e fallback Black–Litterman.
- **Invarianti:**
  - Ogni fattore salva diagnostica in `artifacts/factors/<label>/` con deflated Sharpe e FDR.
  - Stime registrano i parametri in `artifacts/estimates/` con Higham PSD enforcement.
- **Estensioni:** aggiungere fattori in `fair3/engine/factors/core.py` e aggiornarne la validazione in `validation.py`.

## Allocators & Mapping

- **Allocators:**
  - Generatori (`gen_a.py`, `gen_b_hrp.py`, `gen_c_dro.py`, `gen_d_cvar_erc.py`) producono portafogli fattoriali.
  - `meta.py` combina generatori con penalità su turnover/TE.
  - Vincoli in `constraints.py`, obiettivi in `objectives.py`.
- **Mapping:**
  - `rolling_beta_ridge` e `hrp_weights` traducono fattori in strumenti.
  - Guardrail su liquidità (`liquidity.py`) e tracking error (`te_budget.py`).
- **Invarianti:**
  - Gli output sono scritti in `artifacts/weights/` e `artifacts/mapping/` con checksum.
  - Mapping conserva un budget TE massimo e logga i beta CI.
- **Estensioni:** usare `MappingPipelineResult` come contratto; aggiornare README locali con nuovi guardrail.

## Regime, Robustezza, Goals, Execution, Reporting

- **Regime:** `committee.py` fonde segnali (HMM, volatilità, macro slowdown) con isteresi (`hysteresis.py`). Output: probabilità crisi e tilt λ.
- **Robustness:** `lab.py` orchestration di bootstrap, scenari storici e ablazioni; produce PDF e JSON in `artifacts/robustness/`.
- **Goals:** `mc.py` esegue simulazioni Monte Carlo con glidepath; output in `artifacts/goals/` e `reports/`.
- **Execution:** (moduli in `fair3/engine/execution/`) applicano costi, tasse italiane e regola di non scambio.
- **Reporting:** `monthly.py` e `plots.py` generano dashboard CSV/JSON/PDF; `audit.py` consolida check di conformità.
- **Invarianti cross-cutting:**
  - Ogni sottosistema scrive `summary.json` e `metadata.yml` (se applicabile) per arricchire `audit/function_inventory.py`.
  - I report devono poter essere rigenerati offline usando solo `data/clean/` e `artifacts/`.

## Orchestrazione CLI e CI raccomandata

- **CLI:** ogni comando in `fair3/cli/main.py` prepara directories (`ensure_dir`), carica config YAML e chiama la pipeline.
- **CI:** workflow consigliato (`.github/workflows/ci.yml` può essere evoluto) con job sequenziali:
  1. `lint_type`: `ruff check`, `black --check`, `mypy`.
  2. `import_sanity`: `python -m compileall fair3 tests`.
  3. `tests_fast`: `pytest -m "not network"` (matrix su OS/Python).
  4. `coverage_combine + security`: combina XML coverage, esegue `pip-audit`/`bandit`.
  5. `build + codeql`: `python -m build` e analisi CodeQL Python.
- **Workflow separati:**
  - `integration.yml`: cron/manuale per `pytest --network` e ingest smoke test.
  - `release.yml`: build wheel/sdist e `twine upload` su tag annotato.
  - `docs.yml` (opzionale): build statico di `docs/` e pubblicazione su GitHub Pages.

## Linee guida di stile semantico

- **Docstring:** usare convenzione Google (obbligatoria per nuovi moduli). Struttura tipica:
  - Contesto in italiano tecnico.
  - Sezioni `Args`, `Returns`, `Raises`, `Examples` quando utili.
  - Mantenere esempi minimali e auto-consistenti.
- **Type hints:** preferire `from __future__ import annotations` e tipi `Path`, `pandas.DataFrame`, `numpy.ndarray` espliciti.
- **__all__ coerente:** ogni package pubblico (`etl`, `factors`, `allocators`, `mapping`, `regime`, `reporting`, ecc.) deve:
  - Re-exportare solo le API stabilizzate.
  - Aggiornare `COMPONENTS.md` e README locali quando cambia l'interfaccia.
- **Semantica per LLM:** includere esempi minimi nei docstring per ridurre l'esplorazione codice; linkare `audit/function_inventory.py` dai README di sottopacchetto.

## Estensioni suggerite

1. **ADRs:** creare `/DECISIONS/ADR-<id>.md` per documentare scelte (es. motore regime, penalità turnover).
2. **README locali:** ogni sottopacchetto dovrebbe includere tabella con input/output, riferimenti a script QA.
3. **Esempi:** popolare `examples/` con script CLI orchestrati (`python -m fair3.cli.main ingest --help`).
4. **Mappa delle dipendenze:** generare `docs/arch/deps.svg` via `pydeps fair3 --max-bacon=2 --show-deps` e linkarlo da questa pagina.

## Checklist semantica

- [ ] ARCHITECTURE.md aggiornato con pipeline, invarianti ed estensioni.
- [ ] COMPONENTS.md sincronizzato con i moduli principali.
- [ ] GLOSSARY.md copre termini panel/factor/allocator/QA.
- [ ] tests/conftest.py applica marker `network` e opzione CLI.
- [ ] Makefile fornisce target lint/type/test/doc/build.
- [ ] docs/prompt-cheatsheet.md elenca query guida per LLM.
- [ ] __all__ mantenuto coerente nei package pubblici.
- [ ] Docstring Google-style per entry point critici (es. `build_tr_panel`).
- [ ] README di sottosistema collegano `audit/function_inventory.py`.
- [ ] ADRs, examples/ e docs/arch/deps.svg monitorati quando si evolve l'architettura.
