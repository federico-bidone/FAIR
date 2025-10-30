# Report e artefatti

Questo documento riepiloga gli output generati dal layer di reporting di FAIR-III
sia via CLI (`fair3 report`) sia attraverso la GUI.

## Struttura cartelle

```
artifacts/
  reports/
    YYYY-MM-DD_HHMM/
      metrics.csv
      metrics.json
      attribution.csv
      turnover_costs.png
      ...
  logs/
    fair3.log
    metrics.jsonl
```

La GUI crea automaticamente cartelle `YYYY-MM-DD_HHMM` tramite
`fair3.engine.infra.paths.run_dir` ogni volta che viene eseguita la pipeline
automatica.

## Report mensili

`fair3.engine.reporting.generate_monthly_report` riceve una istanza di
`MonthlyReportInputs` e produce i seguenti artefatti:

- `report.html` / `report.pdf` (se la dipendenza `reportlab` è presente)
- `metrics.csv` / `metrics.json`
- `attribution.csv` con contributi fattoriali e strumentali
- `fan_chart.png`, `turnover_costs.png`, `attribution.png`
- `compliance.json` con i flag UCITS/QA

Gli stessi artefatti vengono prodotti quando la GUI genera report sintetici in
assenza di dati reali; questi file fungono da placeholder e verificano che il
contratto di output rimanga stabile.

## Log e metriche

`fair3.engine.logging.setup_logger` scrive i log JSON in `artifacts/logs/fair3.log`
e le metriche in `metrics.jsonl`. La GUI reindirizza anche i log in tempo reale al
pannello console in modo che operatori e test possano monitorare l'avanzamento.

## Collegamento con QA

Il laboratorio di robustezza (`fair3 qa`) e i comandi CLI archiviano gli snapshot
seed/configurazioni nello stesso `artifacts/logs/`. Questo rende semplice
raggruppare report, log e metriche per una determinata run quando si eseguono
verifiche o audit.
