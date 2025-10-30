# Glossario FAIR-III

| Termine | Definizione sintetica |
| --- | --- |
| **Panel (TR panel)** | Dataset point-in-time `asset_panel.parquet` con livelli, rendimenti e feature per simbolo/data/field; garantisce coerenza PIT per tutto lo stack. |
| **Ingest Artifact** | Oggetto `IngestArtifact` con percorso CSV, licenza, checksum e metadati sorgente; popola `data/raw/<source>/`. |
| **TradingCalendar** | Calendario unificato costruito aggregando tutte le date disponibili; definisce l'asse temporale per riallineare prezzi e fattori. |
| **FXFrame** | Contenitore per serie di cambio e valuta base; applica conversioni deterministiche durante l'ETL. |
| **Factor Library** | Collezione di definizioni fattoriali (`FactorDefinition`) con trasformazioni, universe e parametri di validazione. |
| **Factor Pipeline** | Funzione `run_factor_pipeline()` che calcola, valida e rende ortogonali i fattori scrivendo artefatti in `artifacts/factors/`. |
| **Deflated Sharpe Ratio (DSR)** | Statistica che corregge il bias del rapporto di Sharpe in presenza di data snooping; usata per gating QA sui fattori. |
| **White Reality Check** | Test statistico per valutare la significatività di molte strategie simultanee; implementato in `validation.py`. |
| **Estimator Ensemble** | Motori μ/Σ combinati (Ledoit–Wolf, shrinkage, SPD median, Black–Litterman) orchestrati da `fair3 estimate`. |
| **Allocator** | Generatore di portafogli fattoriali (es. HRP, DRO, CVaR-ERC) definito nei moduli `gen_*.py` e coordinato da `meta.py`. |
| **Mapping Pipeline** | Processo che converte pesi fattoriali in pesi strumentali rispettando vincoli ADV/TE (`mapping/pipeline.py`). |
| **Tracking Error Budget** | Limite massimo sullo scostamento rispetto al benchmark; applicato via `enforce_te_budget`. |
| **Regime Committee** | Comitato di segnali di crisi (HMM, vol spike, macro slowdown) che produce probabilità di regime e tilt λ (`regime/committee.py`). |
| **Hysteresis** | Meccanismo di accensione/spegnimento con dwell/cooldown che evita flip frequenti del tilt regime. |
| **Robustness Lab** | Suite di stress test (bootstrap, scenari storici, ablazioni) definita in `robustness/lab.py`. |
| **QA Report** | Oggetto `QAReport` con anomalie, licenze e note ETL registrato in `audit/qa_data_log.csv`. |
| **Audit Trail** | Insieme di snapshot seed, config, checksum e log archiviati in `audit/` per ricostruire ogni run. |
| **Goals Simulation** | Monte Carlo regime-aware con contributi/glidepath (`goals/mc.py`) che restituisce probabilità di successo. |
| **Execution Guardrails** | Regola di non scambio, costi/tasse e bounding ordini applicati in `execution/`. |
| **Function Inventory** | Catalogo `audit/function_inventory.py` con mapping da funzione a artefatto prodotto; usato per audit semantico. |
| **Network Test** | Test marcato `@pytest.mark.network` che richiede accesso internet o API token; escluso per default in CI. |
