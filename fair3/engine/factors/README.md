# Factors Module

## Scopo
Il sottosistema `factors` genera, valida e ortogonalizza le serie di macro-premia utilizzate dagli allocatori. Opera su pannelli PIT prodotti dall'ETL, preservando il determinismo richiesto dall'audit FAIR-III.

- `compute_macro_factors(returns, features, macro=None, seed=None)` restituisce un DataFrame di 10 serie fattoriali (market, momentum, reversal, value, carry, quality, defensive, liquidity, growth, macro overlay) e la relativa lista di `FactorDefinition` con segni economici.
- `FactorLibrary` espone metodi configurabili per generare fattori long/short basati su spread quantili, includendo controlli sui requisiti delle feature.
- `validate_factor_set(factors, asset_returns, n_splits=5, embargo=5, alpha=0.1, seed=None)` esegue CP-CV con embargo, Deflated Sharpe Ratio, White Reality Check semplificato e filtro FDR Benjamini–Hochberg.
- `enforce_orthogonality(factors, corr_threshold=0.9, cond_threshold=50.0)` fonde fattori altamente correlati e applica una rotazione PCA quando necessario per rispettare i vincoli di condizionamento.
- `run_factor_pipeline(...)` orchestri l'intero flusso (lettura pannello clean, generazione fattori, ortogonalizzazione, validazione opzionale, audit snapshot) restituendo `FactorPipelineResult` con i percorsi artefatto.

## Utilizzo CLI
`fair3 factors` è ora cablato al pipeline orchestrator. Esempio:

```powershell
fair3 factors --validate --oos-splits 5 --artifacts-root artifacts/demo
```

Produce i file:

- `artifacts/demo/factors/factors.parquet`
- `artifacts/demo/factors/factors_orthogonal.parquet`
- `artifacts/demo/factors/metadata.json` (comprende segni economici e colonne loadings)
- `artifacts/demo/factors/validation.csv` (se `--validate`)

Ogni esecuzione copia inoltre `configs/*.yml` e `audit/seeds.yml` in `artifacts/audit/` tramite `run_audit_snapshot`.

## Flag `--trace`
I moduli espongono messaggi INFO; il supporto a `--trace` verrà aggiunto quando il CLI sarà esteso. I percorsi delle serie trasformate sono disponibili tramite `orthogonal.loadings` per audit.

## Errori comuni
- **`KeyError: features missing required columns`** – assicurarsi che l'ETL abbia popolato `lag_ma_5`, `lag_ma_21`, `lag_vol_21`.
- **`ValueError: Not enough observations for the requested splits`** – aumentare l'orizzonte dati o ridurre `n_splits`.
- **`ValueError: All factors became degenerate after merging`** – tipicamente dovuto a serie costanti; verificare i dati di input.

## Log e audit
Le funzioni non scrivono file; il chiamante deve serializzare i risultati e aggiornare `artifacts/audit/` (es. copie YAML, loadings PCA). I metadati `FactorDefinition` includono i segni attesi per facilitare controlli di coerenza in `reporting.audit`.
