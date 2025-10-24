# Regime Module

The regime overlay estimates crisis probabilities from market, volatility, and macro
signals before applying hysteresis to generate stable tilt weights for the allocation
stack.

## Public APIs
- `crisis_probability(returns, vol, macro, weights=None) -> pd.Series`: generates a
  crisis probability in \[0, 1\] for the intersection of the provided inputs using a
  deterministic committee (two-state Gaussian HMM over average returns, volatility
  stress via rolling-median normalisation, and macro slowdown scores).
- `CommitteeWeights(hmm=0.5, volatility=0.3, macro=0.2)`: optional weights for the
  committee components. Values are normalised internally and must sum to a positive
  number.
- `apply_hysteresis(p, on, off, dwell_days, cooldown_days) -> pd.Series`: converts the
  probability series into a binary regime flag enforcing `on > off`, minimum dwell
  periods, and cooldown windows.
- `tilt_lambda(p_t) -> float`: linearly maps crisis probability to a tilt factor in
  \[0, 1\] with clamp limits.

## CLI & Integration Notes
- The committee expects PIT returns from the ETL pipeline, realised volatility (or a
  proxy such as 21-day annualised volatility), and macro indicators already aligned
  to the PIT timestamps. Missing data are forward-filled with neutral priors.
- Downstream orchestration will log regime probabilities and hysteresis states under
  `artifacts/audit/regime/` once the CLI wiring lands in later milestones.
- Use `--trace` (planned flag) to echo component scores for debugging: HMM filtered
  state, volatility stress ratio, macro slowdown index, and combined probability.

## Common Errors
- **Empty intersection**: ensure returns/vol/macro share timestamps; otherwise the
  committee returns an empty series.
- **Weights sum to zero**: provide positive committee weights; they are normalised to
  1 internally.
- **Inconsistent hysteresis thresholds**: `on` must exceed `off`; dwell/cooldown must
  be non-negative integers.

## Logging & Audit
- The committee is deterministic; probabilities only depend on inputs and fixed
  parameters, making audit replication straightforward.
- Future integration will persist component contributions and hysteresis state
  transitions into `artifacts/audit/` together with config snapshots.
