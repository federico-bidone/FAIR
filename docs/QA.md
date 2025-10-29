# QA Pipeline

Il comando `fair3 qa` esegue un percorso end-to-end deterministico su un dataset
sintetico (daily business calendar) per verificare che tutti i moduli della
pipeline funzionino anche in assenza di dati reali. Gli artefatti prodotti
abilitano controlli automatici su acceptance gates, robustezza, e auditing.

## Workflow

1. Generazione dati raw sintetici (`raw/`): prezzi log-normali in EUR per tre
   strumenti (`DEMO_EQ`, `DEMO_BOND`, `DEMO_ALT`).
2. ETL (`clean/`): ricostruzione del pannello PIT (`asset_panel.parquet`).
3. Pipeline fattori, stime, ottimizzazione, mapping e regime con audit
   deterministico (seed stream `qa`).
4. Reporting mensile: PDF, CSV/JSON, fan-chart con acceptance gates.
5. Robustness lab: bootstrap, scenari storici, ablation con PDF riassuntivo.

## Artefatti principali

| Path | Descrizione |
| --- | --- |
| `<root>/reports/<period>/monthly_report.pdf` | Report mensile con fan-chart, gate e compliance. |
| `<root>/robustness/robustness_report.pdf` | Sintesi bootstrap + scenari. |
| `<root>/robustness/ablation.csv` | Delta metriche per ciascuna governance feature. |
| `<root>/artifacts/` | Output intermedi (fattori, stime, pesi). |
| `<root>/audit/` | Snapshot di seed/config/checksum per audit trail. |

## Esecuzione

```bash
fair3 qa --label demo --draws 256 --block-size 45
```

Argomenti importanti:

- `--output-dir`: scrive gli artefatti QA in una directory custom (default
  `artifacts/qa/<label>`).
- `--start/--end`: personalizza il calendario sintetico (default 2018-01-01 →
  2021-12-31).
- `--draws/--block-size`: controllano bootstrap draws e dimensione dei blocchi
  per il robustness lab.
- `--validate-factors`: abilita la cross-validation dei fattori (disattivata di
  default per velocizzare i test CI).
- `--seed`: forza un seed numerico, bypassando `audit/seeds.yml`.

## Output booleani

La funzione `run_demo_qa` restituisce `DemoQAResult` con i flag
`acceptance_passed` e `robustness_passed`. I test di integrazione e la CLI
registrano anche metriche in `artifacts/audit/metrics.jsonl` per facilitare gli
assert di CI.

## FAQ

- **Quanto dura l'esecuzione?** Con i parametri default su laptop moderno < 1
  minuto; per CI usare `--draws 32 --block-size 12`.
- **È necessario l'accesso a internet?** No, tutti i dati sono sintetici.
- **Posso cambiare i simboli?** Al momento no; i simboli sono fissati per
  garantire determinismo in test/regressioni.
- **Gli artefatti sovrascrivono run precedenti?** Sì, il comando ricrea la
  directory `--output-dir` mantenendo determinismo.

> Strumento informativo/educational; non costituisce consulenza finanziaria o
> raccomandazione.
