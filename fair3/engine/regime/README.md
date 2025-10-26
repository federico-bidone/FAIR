# Regime Module

The regime engine combines a Gaussian HMM on returns, a volatility HSMM proxy and
macro slowdown triggers to estimate crisis probabilities. A configurable hysteresis
layer enforces on/off streaks, dwell time and cool-down windows before exposing the
binary regime flag to downstream allocation stages.

## Public APIs
- `regime_probability(panel, cfg, seed) -> pd.DataFrame`: main entrypoint returning
  a DataFrame with columns `p_crisis`, `p_hmm`, `p_volatility`, `p_macro`,
  `hmm_state`, `vol_state`, `macro_trigger` and `regime_flag`. The input `panel`
  should expose `returns`, `volatility` and `macro` sections (multi-index columns
  created via `pd.concat({"returns": df_returns, ...}, axis=1)`).
- `run_regime_pipeline(clean_root=..., thresholds_path=..., output_dir=..., seed=...)`:
  orchestrates data loading from the clean PIT panel, applies the committee, writes
  CSV artefacts under `artifacts/regime/` and returns a `RegimePipelineResult` with
  the probability frame.
- `crisis_probability(returns, vol, macro, weights=None) -> pd.Series`: backwards
  compatible wrapper returning only the combined probability series. Internally it
  delegates to `regime_probability` using default thresholds.
- `CommitteeWeights(hmm=0.5, volatility=0.3, macro=0.2)`: optional component weights
  for the committee. The `normalised()` helper rescales them to sum to one.
- `apply_hysteresis(p, on, off, dwell_days, cooldown_days, activate_streak,
  deactivate_streak) -> pd.Series`: converts probabilities into a binary flag while
  enforcing minimum streaks, dwell time and cool-down periods.
- `tilt_lambda(p_t) -> float`: maps a crisis probability to a tilt coefficient in
  `[0, 1]` for allocation overlays.

## CLI & Integration Notes
- `fair3 regime --dry-run` loads the clean panel, applies the thresholds defined in
  `configs/thresholds.yml`, persists CSV artefacts (`probabilities.csv`,
  `hysteresis.csv`, `committee_log.csv`) and prints the latest crisis probability
  together with the active thresholds. Use `--trace` to print the tail of the
  probability frame to stdout.
- The panel expects PIT-aligned inputs: returns (e.g. `log_ret` unstacked by symbol),
  realised volatility proxies (e.g. `lag_vol_21`) and macro features (`inflation_yoy`,
  `pmi`, `real_rate`). Missing sections are imputed deterministically using
  synthetic series so tests remain reproducible.
- Thresholds are validated by `fair3 validate`. Ensure `activate_streak` and
  `deactivate_streak` reflect the desired consecutive-observation requirements.

## Common Errors
- **Empty intersection**: if returns, volatility and macro sections do not share
  timestamps the engine returns an empty frame.
- **Weights sum to zero**: provide positive committee weights; they are normalised
  internally to avoid division by zero.
- **Invalid hysteresis parameters**: `on` must exceed `off`, dwell/cooldown must be
  non-negative and streak parameters must be at least one observation.

## Logging & Audit
- The pipeline logs deterministic JSON/console records via `fair3.engine.logging` and
  writes artefacts in `artifacts/regime/`. Metrics include `regime_p_crisis` to track
  the latest probability.
- Component contributions (`p_hmm`, `p_volatility`, `p_macro`) are stored in
  `committee_log.csv` to support forensic analysis and acceptance gates.
