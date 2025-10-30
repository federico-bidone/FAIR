# Prompt cheat-sheet per FAIR-III

Usa queste domande come partenza per interrogare un LLM sulla codebase. Ogni prompt è pensato per recuperare rapidamente contesto dai file di riferimento.

## Architettura generale
- "Riepiloga il flusso ingest → etl → factors → allocators → reporting utilizzando ARCHITECTURE.md e COMPONENTS.md."
- "Quali sono gli invarianti di audit e determinismo descritti in ARCHITECTURE.md?"
- "Mostra la checklist semantica e verifica quali elementi sono già implementati."

## Ingest e dati
- "Elenca i fetcher disponibili e le relative licenze usando COMPONENTS.md e fair3/engine/ingest/registry.py."
- "Come si aggiunge un nuovo fetcher? Indica i passi descritti in ARCHITECTURE.md e gli hook in registry.py."
- "Quali test sono marcati come di rete e come abilitarli in pytest? Consulta tests/conftest.py."

## ETL e pannello dati
- "Descrivi come TRPanelBuilder costruisce asset_panel.parquet e quali checksum produce (fair3/engine/etl/make_tr_panel.py)."
- "Che ruolo ha FXFrame nella conversione delle serie valutarie?"
- "Mostra un esempio di QAReport generato e dove viene salvato."

## Fattori e stime
- "Quali fattori macro sono definiti in fair3/engine/factors/core.py e come vengono validati?"
- "Come funziona il deflated Sharpe ratio e dove viene calcolato (validation.py)?"
- "Qual è il flusso di fallback Black–Litterman descritto in ARCHITECTURE.md?"

## Allocazione e mapping
- "Spiega la differenza tra gen_b_hrp.py e gen_c_dro.py nel pacchetto allocators." 
- "Come viene imposto il budget di tracking error in mapping/te_budget.py?"
- "Quali artefatti vengono scritti da mapping/pipeline.py e dove sono localizzati?"

## Regime, robustezza, goals
- "Quali segnali compongono il committee di regime (regime/committee.py) e come agisce l'isteresi?"
- "In che modo robustness/lab.py orchestra bootstrap e scenari storici?"
- "Quali parametri governano la simulazione goals/mc.py e quali file di configurazione utilizza?"

## Reporting, execution, QA
- "Quali passi generano il report mensile e quali file vengono creati da reporting/monthly.py?"
- "Come viene applicata la regola di non scambio nel livello di execution?"
- "Come è mantenuto audit/function_inventory.py e da quali README viene referenziato?"

## Manutenzione e CI
- "Quali target fornisce il Makefile e come si mappano sui job CI suggeriti?"
- "Come integrare nuovi ADR nella cartella DECISIONS secondo ARCHITECTURE.md?"
- "Quali convenzioni docstring/type hints devono essere rispettate nei nuovi moduli?"

Personalizza questi prompt aggiungendo `Mostra frammenti di codice` o `Analizza la complessità` per ottenere risposte più dettagliate dal modello.
