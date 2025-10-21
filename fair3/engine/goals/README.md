# Goals Module

## Scopo
Il modulo `fair3.engine.goals` fornisce il motore Monte Carlo per la
valutazione dei goal household, producendo probabilità di successo
ponderate e una glidepath deterministica in linea con i vincoli FAIR-III.
Il simulatore supporta input UCITS retail, integra contributi mensili e
utilizza curve di regime sintetiche (base/crisi) seedate in modo
riproducibile.

## API Pubbliche
- `run_goal_monte_carlo(goals, draws, seed, monthly_contribution, ...)`:
  esegue la simulazione completa scrivendo CSV/PDF in
  `artifacts/goals/` (o nella directory specificata).
- `simulate_goals(...)`:
  restituisce la `GoalSimulationSummary` con probabilità per goal e
  glidepath senza produrre artefatti.
- `load_goal_configs_from_yaml(path)` / `load_goal_parameters(path)`:
  helper per leggere i file YAML di configurazione (`configs/goals.yml`
  e `configs/params.yml`).
- `build_contribution_schedule(...)` e `build_glidepath(...)`:
  utility deterministiche riutilizzabili in test e analisi.

Tutte le API accettano un parametro `seed` propagato tramite
`numpy.random.SeedSequence` per garantire risultati identici a parità di
input.

## Esempi
### CLI
```bash
fair3 goals --draws 12000 --seed 21 --output-dir artifacts/goals_run
```
### Python
```python
from fair3.engine.goals import load_goal_configs_from_yaml, run_goal_monte_carlo

goals = load_goal_configs_from_yaml("configs/goals.yml")
summary, artifacts = run_goal_monte_carlo(
    goals,
    draws=16000,
    seed=7,
    monthly_contribution=500.0,
    initial_wealth=10_000.0,
)
print(summary.results[["goal", "probability", "passes"]])
print("PDF:", artifacts.report_pdf)
```

## Flag & Tracing
- `--draws`, `--seed`, `--output-dir`: controllano il volume di
  simulazioni, il seed RNG e la directory di destinazione.
- `--monthly-contribution`, `--initial-wealth`,
  `--contribution-growth`: override CLI per scenari what-if.
- Log sintetico in stdout come `[fair3] goals draws=... weighted=...`.

## Errori Comuni
- Nessun goal configurato ⇒ il comando termina con errore esplicito.
- Directory output non scrivibile ⇒ eccezione Python; assicurarsi di
  avere permessi adeguati.
- Numero di `draws` troppo elevato ⇒ tempi di esecuzione prolungati;
  usare valori più bassi in test locali (<5k) e lasciare 10k+ per CI.

## Tracciamento & Log
Gli artefatti `summary.csv`, `glidepath.csv`, `report.pdf` vengono
scritti in `artifacts/goals/` (o percorso custom). I file riportano seed
utilizzato e probabilità per ciascun goal per favorire auditabilità.
