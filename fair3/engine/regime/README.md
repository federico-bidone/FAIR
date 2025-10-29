# Modulo Regime

Il motore del regime combina un HMM gaussiano sui rendimenti, un proxy HSMM per la volatilità e trigger di rallentamento macro
per stimare le probabilità di crisi. Un livello di isteresi
configurabile applica serie di attivazione/disattivazione, tempo di permanenza e finestre di raffreddamento prima di esporre il flag del regime binario
alle fasi di allocazione downstream.

## API pubbliche
- `regime_probability(panel, cfg, seed) -> pd. DataFrame`: ritorno del punto di ingresso principale
  un DataFrame con colonne `p_crisis`, `p_hmm`, `p_volatility`, `p_macro`,
  `hmm_state`, `vol_state`, `macro_trigger` e `regime_flag`.L'input `panel`
  deve esporre le sezioni `returns`, `volatility` e `macro` (colonne multiindice
  create tramite `pd.concat({"returns": df_returns, ...}, axis=1)`).
- `run_regime_pipeline(clean_root=..., thresholds_path=..., output_dir=..., seed=...)`:
  orchestra il caricamento dei dati dal pannello PIT pulito, applica il comitato, scrive
  CSVartefatti in `artifacts/regime/` e restituisce un `RegimePipelineResult` con
  il quadro di probabilità.
- `crisis_probability(returns, vol, macro, weights=None) -> pd. Series`: all'indietro
  wrapper compatibile che restituisce solo la serie di probabilità combinata. Internamente
  delega a `regime_probability` utilizzando soglie predefinite.
- `CommitteeWeights(hmm=0.5, volatility=0.3, macro=0.2)`: pesi dei componenti opzionali
  per il comitato. L'helper `normalised()` li ridimensiona per sommarli a uno.
- `apply_hysteresis(p, on, off, dwell_days, cooldown_days, activate_streak,
  deactivate_streak) -> pd. Series`: converte le probabilità in un flag binario mentre
  applica serie minime, tempo di sosta e raffreddamentoperiodi.
- `tilt_lambda(p_t) -> float`: associa una probabilità di crisi a un coefficiente di inclinazione in
  `[0, 1]` per sovrapposizioni di allocazione.

## CLI e note di integrazione
- `fair3 regime --dry-run` carica il pannello pulito, applica le soglie definite in
  `configs/thresholds.yml`, persiste gli artefatti CSV (`probabilities.csv`,
  `hysteresis.csv`, `committee_log.csv`) e stampa l'ultima crisiprobabilità
  insieme alle soglie attive. Utilizzare `--trace` per stampare la coda del frame di probabilità
  su stdout.
- Il pannello si aspetta input allineati PIT: rendimenti (ad es. `log_ret` non impilati per simbolo),
  proxy della volatilità realizzata (es. `lag_vol_21`) e caratteristiche macro (`inflation_yoy`,
  `pmi`, `real_rate`).Le sezioni mancanti vengono imputate in modo deterministico utilizzando
  serie sintetiche in modo che i test rimangano riproducibili.
- Le soglie sono convalidate da `fair3 validate`.Assicurati che `activate_streak` e
  `deactivate_streak` riflettano i requisiti di osservazione consecutiva desiderati.

## Errori comuni
- **Intersezione vuota**: se rendimenti, volatilità e sezioni macro non condividono
  timestamp, il motore restituisce un fotogramma vuoto.
- **Somma dei pesi a zero**: fornire pesi positivi al comitato; sono normalizzati
  internamente per evitare la divisione per zero.
- **Parametri di isteresi non validi**: `on` deve superare `off`, la pausa/raffreddamento deve essere
  non negativo e i parametri di serie devono essere almeno un'osservazione.

## Logging e controllo
- La pipeline registra i record JSON/console deterministici tramite`fair3.engine.logging` e
  scrive artefatti in `artifacts/regime/`.Le metriche includono `regime_p_crisis` per monitorare
  l'ultima probabilità.
- I contributi dei componenti (`p_hmm`, `p_volatility`, `p_macro`) vengono archiviati in
  `committee_log.csv` per supportare l'analisi forense e i gate di accettazione.
