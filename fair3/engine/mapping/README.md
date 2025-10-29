# Modulo di mappatura

## Scopo
Il livello di mappatura converte i portafogli fattoriali in esposizioni di strumenti implementabili.
Fornisce stima deterministica del beta, dimensionamento in base alla liquidità e tracking-error
controlli prima dell'esecuzione.

## API pubblica
- `rolling_beta_ridge(rendimenti, fattori, finestra, lambda_beta, sign_prior=None,
  enforce_sign=True)` stima i beta rolling ridge sotto il segno economico opzionale
  vincoli.
- `beta_ci_bootstrap(returns, factors, beta_ts, B=1000, alpha=0.2)`
  genera intervalli di confidenza per limitare le esposizioni rumorose.
- `cap_weights_by_beta_ci(weights, beta_ci, tau_beta)` ridimensiona lo strumento
  ponderazioni quando gli intervalli di confidenza sono ampi.
- `hrp_weights(Sigma, labels)` calcola i pesi di parità gerarchica del rischio intra-fattore.
- `tracking_error(weights, baseline, Sigma)` valuta TE per fattorebudget.
- `enforce_te_budget(exposures, target_exposure, te_factor_max)` fattore di bloccaggio
  deviazioni, mentre `enforce_portfolio_te_budget(weights, baseline, Sigma, cap)`
  riduce le esposizioni fino al raggiungimento del limite di tracking-error del portafoglio.
- `max_trade_notional(adv, prices, cap_ratio)` deriva i limiti nozionali ADV.
- `clip_trades_to_adv(delta_w, portfolio_value, adv, prices, cap_ratio)` ridimensiona le operazioni
  per rispettare le soglie ADV senza invertire i segni.
- `run_mapping_pipeline(...)` orchestri il mapping fattore→strumentoe restituisce
  `MappingPipelineResult` con percorsi per beta, CI e pesi strumentali.

## CLI Hooks
`fair3 map --hrp-intra --adv-cap 0.05` invoca il pipeline orchestrator e produce:

- `artifacts/mapping/rolling_betas.parquet`
- `artifacts/mapping/beta_ci.parquet`
- `artifacts/mapping/summary.json` (TE prima/dopo)
- `artifacts/weights/instrument_allocation.csv`

Le soglie TE/ADV sono lette da `configs/thresholds.yml` e ogni run registra audit snapshot
dei fileYAML e dei checksum degli artefatti.

## Trace Flags
Il modulo rispetta la configurazione globale di registrazione/traccia; impostare `--trace` sulla CLI per
emettere diagnostica della finestra beta e aggiustamenti TE/liquidità.

## Errori comuni
- Gli indici disallineati tra rendimenti e fattori determinano `ValueError`.
- L'utilizzo di una finestra più grande della cronologia disponibile genera un'eccezione.
- Caps ADV negativi o valori di portafoglio attivano la convalidaerrori.

I log e la diagnostica bootstrap vengono scritti in `artifacts/audit/` tramite lo stack di reporting
per facilitare le revisioni post-negoziazione.
