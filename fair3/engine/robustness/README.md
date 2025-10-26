# Modulo Robustezza

Questa sottocartella raccoglie gli strumenti che mettono alla prova le
allocazioni FAIR-III con analisi "what-if" e backtest sintetici. Tutte le
funzioni espongono docstring e logging in italiano per agevolare il debugging
operativo.

## API Pubblica

### `fair3.engine.robustness.bootstrap`
- `block_bootstrap_metrics(...)`: esegue un bootstrap a blocchi sui rendimenti
  e restituisce le statistiche campionate insieme alle soglie di accettazione.
- `RobustnessGates`: dataclass che incapsula le soglie di superamento dei test.

### `fair3.engine.robustness.scenarios`
- `ShockScenario`: rappresenta uno shock stilizzato con rendimenti precalcolati.
- `default_shock_scenarios()`: fornisce gli shock storici inclusi di default.
- `replay_shocks(...)`: riapplica gli shock sui rendimenti osservati
  calcolando drawdown e CAGR.

### `fair3.engine.robustness.ablation`
- `run_ablation_study(...)`: valuta la sensibilità delle metriche disattivando
  una feature per volta.
- `AblationOutcome`: ritorna la tabella riassuntiva delle prove.
- `DEFAULT_FEATURES`: elenco ordinato delle feature governative di riferimento.

### `fair3.engine.robustness.lab`
- `RobustnessConfig`: configura la dimensione dei blocchi, il numero di
  estrazioni e le soglie di accettazione.
- `RobustnessArtifacts`: descrive i file generati dal laboratorio di robustezza.
- `run_robustness_lab(...)`: orquestra bootstrap, scenari e (facoltativamente)
  ablation, producendo CSV, JSON e un PDF riassuntivo.

## Utilizzo da Pipeline/CLI

L'orchestratore invoca `run_robustness_lab` dopo il reporting mensile per
produrre diagnostiche in `artifacts/robustness/`. È possibile passare una
callback `ablation_runner` che riceve i flag di governance e ritorna metriche
(Sharpe, tracking error, drawdown). Il laboratorio crea automaticamente una
cartella dedicata e popola i file in modo deterministico se si fornisce un
`seed`.

```python
from fair3.engine.robustness import RobustnessConfig, run_robustness_lab


def valuta_assetto(flag_set: dict[str, bool]) -> dict[str, float]:
    """Simula un punteggio di robustezza in base ai flag governativi."""
    # Qui andrebbe invocata la pipeline principale in modalità analisi.
    return {"sharpe": 0.84, "max_drawdown": -0.23}


artifacts, gates = run_robustness_lab(
    returns=serie_rendimenti,
    config=RobustnessConfig(draws=256, block_size=60),
    seed=42,
    ablation_runner=valuta_assetto,
)
print("Gates superati:", gates.passes())
```

## Errori Comuni e Troubleshooting

| Sintomo | Possibile causa | Risoluzione |
| --- | --- | --- |
| `ValueError` sulla dimensione del blocco | Il blocco richiesto è più grande del campione | Ridurre `block_size` o aggregare i rendimenti |
| Tabella di ablation vuota | La callback non restituisce metriche | Verificare che il runner ritorni un dict di float |
| PDF mancante | Backend Matplotlib non disponibile | Installare `matplotlib` e lasciare attivo il backend `Agg` |

## Tracciamento e Audit

Impostando `seed` o affidandosi a `audit/seeds.yml` si ottengono risultati
riproducibili per bootstrap e scenari. Le pipeline dovrebbero loggare i path
prodotti tramite `fair3.engine.logging.setup_logger` (con `--json-logs` quando
serve l'audit trail completo) anche in modalità `--trace`.
