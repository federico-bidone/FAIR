# Goals Module

## Scopo
Il modulo `fair3.engine.goals` fornisce il motore Monte Carlo per la
valutazione dei goal household, producendo probabilità di successo
ponderate, fan-chart e glidepath adattive coerenti con i vincoli FAIR-III.
Il simulatore supporta piani di contribuzione e riscatti programmati,
integra curve di regime (base/crisi) e consente di applicare glidepath
più conservativi o aggressivi in base alla probabilità di raggiungimento
dei target.

## API Pubbliche
- `run_goal_monte_carlo(goals, draws, seed, parameters, ...)`:
  esegue la simulazione completa scrivendo CSV/PDF in `reports/`
  (o nella directory specificata) con nomi basati sull'investor.
- `goal_monte_carlo(parameters, goals, draws=..., seed=..., regime_panel=None)`:
  restituisce un payload serializzabile con risultati, glidepath e fan-chart
  senza produrre artefatti.
- `simulate_goals(goals, draws, seed, parameters, assumptions=None, regime_panel=None)`:
  restituisce `GoalSimulationSummary` con per-goal stats, glidepath e fan-chart.
- `load_goal_configs_from_yaml(path)` / `load_goal_parameters(path)`:
  helper per leggere i file YAML di configurazione (`configs/goals.yml`
  e `configs/params.yml`).
- `build_contribution_schedule(...)`, `build_withdrawal_schedule(...)` e
  `build_cashflow_schedule(...)`: utility deterministiche riutilizzabili in test
  e analisi.

Tutte le API accettano un parametro `seed` propagato tramite
`numpy.random.SeedSequence` per garantire risultati identici a parità di
input.

## Esempi
### CLI
```bash
fair3 goals --simulate --draws 12000 --seed 21 --output-dir reports/demo
```
### Python
```python
from fair3.engine.goals import (
    GoalParameters,
    load_goal_configs_from_yaml,
    run_goal_monte_carlo,
)

goals = load_goal_configs_from_yaml("configs/goals.yml")
parameters = GoalParameters.from_mapping(
    {
        "investor": "household_alpha",
        "contrib_monthly": 500.0,
        "contribution_growth": 0.02,
        "initial_wealth": 15_000.0,
        "contribution_plan": [{"start_year": 10, "end_year": 15, "amount": 1_000.0}],
        "withdrawals": [{"year": 30, "amount": 300_000.0}],
    }
)
summary, artifacts = run_goal_monte_carlo(
    goals,
    draws=16000,
    seed=7,
    parameters=parameters,
)
print(summary.results[["goal", "probability", "passes"]])
print("PDF:", artifacts.report_pdf)
```

## Flag & Tracing
- `--draws`, `--seed`, `--output-dir`: controllano il volume di
  simulazioni, il seed RNG e la directory di destinazione.
- `--simulate`: richiesto per eseguire la simulazione; senza flag il CLI
  mostra solamente il numero di goal configurati.
- `--monthly-contribution`, `--initial-wealth`,
  `--contribution-growth`: override CLI del piano household.
- Log sintetico in stdout come
  `[fair3] goals investor=... draws=... weighted=... pdf=... fan=...`.

## Errori Comuni
- Nessun goal configurato ⇒ il comando termina con errore esplicito.
- Directory output non scrivibile ⇒ eccezione Python; assicurarsi di
  avere permessi adeguati.
- Numero di `draws` troppo elevato ⇒ tempi di esecuzione prolungati;
  usare valori più bassi in test locali (<5k) e lasciare 10k+ per CI.

## Tracciamento & Log
Gli artefatti `*_summary.csv`, `*_glidepaths.csv`, `*_fan_chart.csv` e
`goals_<investor>.pdf` vengono scritti in `reports/` (o percorso custom).
I file riportano seed utilizzato, probabilità per ciascun goal, glidepath
adattivo e fan-chart 5/50/95 per favorire auditabilità e analisi what-if.
