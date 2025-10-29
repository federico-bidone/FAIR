# Modulo Stime

## Scopo
La sezione *stime* fornisce gli strumenti per costruire matrici di covarianza
e tempi delle attese replicabili monitorandone la stabilità nel tempo. Le routine
coperte in questa pietra miliare includono:

- **Ledoit–Wolf**: restringimento verso l'identità con PSD forzata.
- **Graphical Lasso** con selezione BIC: stima sparsa sul campione centrato.
- **Factor restringimento**: ricostruzione tramite componenti principali con rumore
  idiosincratico positivo.
- **Mediana element-wise** e **EWMA regime-aware** per aggregare più matrici
  mantenendo la proprietà PSD.
- **Mediana geometrica SPD** opzionale (`--sigma-engine spd_median`) con
  fallback PSD automatico in caso di mancata convergenza.
- **Ensemble μ**: Shrink-to-zero, bagging OLSe gradient boosting combinati via
  stacking ridge deterministico.
- **Black–Litterman**: recupero di μ_eq dal portafoglio di mercato e blend con
  fallback automatico se l'information ratio della view è sotto soglia.
- **Drift metrics**: Frobenius relativo e massimo scostamento di correlazione per
overlay di rischio ed esecuzione.

Tutte le uscite passano per `project_to_psd` per rispetto i gate di
accettazione Σ ≥ 0.

## API principali
```python
from fair3.engine.estimates import (
    blend_mu,
    ewma_regime,
    estimate_mu_ensemble,
    factor_shrink,
    frobenius_relative_drift,
    graphical_lasso_bic,
    ledoit_wolf,
    median_of_covariances,
    max_corr_drift,
    run_estimate_pipeline,
    reverse_opt_mu_eq,
    sigma_consensus_psd,
    sigma_spd_median,
)
```

## Pipeline &CLI
Il comando `fair3 estimate` invoca `run_estimate_pipeline`, che legge i fattori
ortogonalizzati da `artifacts/factors/`, produce `mu_post.csv`, `mu_star.csv`,
`mu_eq.csv`, `sigma.npy`, `blend_log.csv`, e aggiorna `risk/sigma_drift_log.csv`
quando sono disponibili tempi precedenti. Gli snapshot di seed/config vengono
salvati automaticamente tramite `reporting.audit.run_audit_snapshot`.

Esempio CLI con root personalizzato:

```powershell
fair3 estimate --artifacts-root artifacts/demo --thresholds configs/thresholds.yml --cv-splits 5 --sigma-engine spd_median
```

## Flag `--trace`
Il flag `--trace` verrà aggiunto nelle prossime iterazioni per salvare log e
matrici intermedie in `artifacts/estimates/`.Le chiamate dirette possono già
salvare gli output utilizzando `fair3.engine.utils.artifact_path`.

## Errori comuni
- `ValueError`: dataframe vuoto o con `NaN` → assicurarsi che l'ETL abbia
  completato la pulizia.
- `RuntimeError` nella grafica lasso: tutti i `lambda` candidati fallito la
  hanno convergenza; ampliare la griglia o controllare la PSD del campione.
- Dimensioni non coerenti in `ewma_regime` o nelle metriche di drift.

## Log e audit
Le routine non scrivono direttamente su disco ma restituiscono matrici
`numpy`.È responsabilità dell'orchestratore salvare i risultati e registrare i
parametri in `artifacts/audit/` tramite `reporting.audit`.
