# Modulo Allocatori

Il pacchetto allocatori ospita i motori di costruzione del portafoglio FAIR-III.Ciascun generatore rispetta i vincoli di implementabilità al dettaglio (long-only, limiti di fatturato/TE/ADV) consentendo al tempo stesso combinazioni di rendimenti di fattori o strumenti sensibili al rischio.

## API pubbliche

| Funzione | Descrizione |
| --- | --- |
| `risk_contributions(w, Sigma)` | Contributi al rischio marginale \(RC_i = w_i (\Sigma w)_i\). |
| `balance_clusters(w, Sigma, clusters, tol)` | Ridimensiona iterativamente i pesi dei cluster finché la deviazione ERC non rientra in `tol`. |
| `generator_A(mu, Sigma, constraints)` | Massimizza Sharpe con la penalità DRO di Wasserstein, i limiti CVaR/EDaR, i vincoli di turnover e leva finanziaria, quindi bilancia i cluster ERC. |
| `generator_B_hrp(Sigma)` | Linea di base della parità gerarchica del rischio (collegamento dei reparti, quasi-diagonalizzazione). |
| `generator_C_dro_closed(mu, Sigma, gamma, rho)` | Portafoglio distributivamente robusto in forma chiusa tramite inverso regolarizzato a cresta. |
| `generator_D_cvar_erc(mu, Sigma, constraints)` | Allocazione per minimizzare il CVaR con bilanciamento dei cluster ERC e limiti di leva finanziaria/fatturato. |
| `fit_meta_weights(returns_by_gen, sigma_matrix, j_max, penalty_to, penalty_te, baseline_idx)` | Meta-learner che unisce i PnL del generatore con le penalità di turnover/TE sul simplex. |
| `run_optimization_pipeline(...)` | Wrapper che esegue generatori, meta-learner opzionale e persiste artefatti/audit (`OptimizePipelineResult`). |

## CLI / Integrazione

`fair3 optimize --generators A, B, C --meta` invoca il pipeline orchestrator e produce:

- `artifacts/weights/generator_*.csv` (pesi per singolo generatore)
- `artifacts/weights/factor_allocation.csv` (allocazione finale)
- `artifacts/weights/allocation_diagnostics.csv` (RC per fattore)
- `artifacts/weights/meta_weights.csv` se `--meta`

Audit snapshot e checksum sono registrati automaticamente.

## Determinismo e semi

Tutti i solutori sono deterministici quando alimentati con input deterministici. Le estrazioni degli scenari devono provenire da `utils.rand.generator_from_seed`.La casualità del risolutore è disabilitata dai back-end convessi (SCS/ECOS).

## Errori comuni

- **Vincoli CVaR non realizzabili:** assicurano che `constraints["scenario_returns"]` abbia una cronologia adeguata; allentare leggermente `cvar_cap` o fornire più scenari.
- **Violazione del fatturato dopo il bilanciamento ERC:** il generatore riduce la mossa post-bilanciamento se il fatturato supera il limite. Fornire `turnover_cap` realistici (>0, 01) per evitare degenerazioni.
- **Casi limite HRP per asset singolo:** il generatore HRP restituisce `[1.0]` quando è presente un solo asset.

## Flag di tracciamento

Passa `constraints["trace"] = True` per ricevere messaggi di stato del risolutore e diagnostica del cluster nel file di registro dell'allocatore.
