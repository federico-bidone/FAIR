# Modulo QA pipeline

> Strumento informativo/didattico; non contiene consulenza finanziaria o raccomandazione.

Il motore QA crea un set di dati sintetici deterministici, esegue l'intera pipeline
FAIR-III ed emette artefatti di audit che confermano l'accettazione e
gate di robustezza. È il flusso di lavoro di riferimento per la convalida delle installazioni e
per il debug delle regressioni end-to-end senza colpire i fornitori di dati esterni.

## Componenti chiave
- `DemoQAConfig`: configurazione immutabile per lo scenario QA (calendario, etichetta,
  controlli bootstrap, soglie di accettazione e flusso di seed).
- `DemoQAResult`: raccolta di percorsi di output e flag pass/fail visualizzati dal gestore
  CLI.
- `run_demo_qa`: orchestra l'acquisizione di scaffolding, ETL, fattori, stime,
  ottimizzazione, mappatura, sovrapposizione del regime, reporting e laboratorio di robustezza suil
  set di dati sintetici.

## Utilizzo
```bash
fair3 qa --label demo --draws 256 --block-size 45 --validate-factors
```

Il comando scrive gli artefatti in `artifacts/qa/<label>/` per impostazione predefinita. Sostituisci il
location con `--output-dir` per mantenere le esecuzioni del QA isolate dagli artefatti di produzione.
Tutti gli output includono metadati di checksum in modo che possano essere differenziati tra le versioni.
