# Estimates Module

## Scopo
La sezione *estimates* fornisce gli strumenti per costruire matrici di covarianza
e stime delle attese replicabili monitorandone la stabilità nel tempo. Le routine
coperte in questa milestone includono:

- **Ledoit–Wolf**: shrinkage verso l'identità con PSD forzata.
- **Graphical Lasso** con selezione BIC: stima sparsa sul campione centrato.
- **Factor shrinkage**: ricostruzione tramite componenti principali con rumore
  idiosincratico positivo.
- **Mediana element-wise** e **EWMA regime-aware** per aggregare più matrici
  mantenendo la proprietà PSD.
- **Ensemble μ**: shrink-to-zero, bagging OLS e gradient boosting combinati via
  stacking ridge deterministico.
- **Black–Litterman**: recupero di μ_eq dal portafoglio di mercato e blend con
  fallback automatico se l'information ratio della view è sotto soglia.
- **Drift metrics**: Frobenius relativo e massimo scostamento di correlazione per
overlay di rischio ed execution.

Tutte le uscite passano per `project_to_psd` per rispettare i gate di
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
)
```

## Pipeline & CLI
Il comando `fair3 estimate` invoca `run_estimate_pipeline`, che legge i fattori
ortogonalizzati da `artifacts/factors/`, produce `mu_post.csv`, `mu_star.csv`,
`mu_eq.csv`, `sigma.npy`, `blend_log.csv`, e aggiorna `risk/sigma_drift_log.csv`
quando sono disponibili stime precedenti. Gli snapshot di seed/config vengono
salvati automaticamente via `reporting.audit.run_audit_snapshot`.

Esempio CLI con root personalizzato:

```powershell
fair3 estimate --artifacts-root artifacts/demo --thresholds configs/thresholds.yml --cv-splits 5
```

## Flag `--trace`
Il flag `--trace` verrà aggiunto nelle prossime iterazioni per salvare log e
matrici intermedie in `artifacts/estimates/`. Le chiamate dirette possono già
salvare gli output usando `fair3.engine.utils.artifact_path`.

## Errori comuni
- `ValueError`: dataframe vuoto o con `NaN` → assicurarsi che l'ETL abbia
  completato la pulizia.
- `RuntimeError` nella grafica lasso: tutti i `lambda` candidati hanno fallito la
  convergenza; ampliare la griglia o controllare la PSD del campione.
- Dimensioni non coerenti in `ewma_regime` o nelle metriche di drift.

## Log e audit
Le routine non scrivono direttamente su disco ma restituiscono matrici
`numpy`. È responsabilità dell'orchestratore salvare i risultati e registrare i
parametri in `artifacts/audit/` tramite `reporting.audit`.
