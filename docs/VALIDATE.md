# Configuration validation (`fair3 validate`)

The `fair3 validate` command performs a schema audit on the core configuration files used by the
FAIR-III portfolio engine. It is the recommended pre-flight step before running ETL, factor, or
optimisation pipelines because it catches malformed YAML entries early.

## Usage

```bash
fair3 validate \
  --params configs/params.yml \
  --thresholds configs/thresholds.yml \
  --goals configs/goals.yml \
  --verbose
```

* `--params`, `--thresholds`, `--goals` allow overriding the default configuration locations.
* `--verbose` prints the parsed payloads so the operator can review defaults and derived fields.

Exit status is `0` when validation succeeds. Schema or file errors are written to stdout with an
`[fair3] validate error: ...` prefix and the command exits with status `1`.

## Schema summary

| File | Required keys | Notes |
| ---- | ------------- | ----- |
| `params.yml` | `currency_base`, `household`, `rebalancing` | `currency_base` must be an ISO code; `household` now includes the optional fields `investor`, `contribution_plan` (rules with `start_year`/`end_year`/`frequency`), and `withdrawals`; `rebalancing.no_trade_bands` is capped at 50 bps. |
| `thresholds.yml` | `vol_target_annual`, `tau`, `execution`, `regime`, `drift` | `regime.on` must exceed `regime.off`; activation/deactivation streaks are ≥1; committee weights and macro weights must sum to positive values; turnover, tracking-error and ADV caps stay within [0, 1]; the annual volatility target is clamped between 1% and 50%. |
| `goals.yml` | `goals` (non-empty list) | Each goal requires `name`, `W`, `T_years`, `p_min`, `weight`. Probabilities sit in [0, 1]; weights are checked for near-unity sums with a 5% tolerance. |

Warnings (for example imbalanced goal weights) are reported but do not fail validation. Treat them as
prompts to revisit the configuration before executing the full pipeline.

All validation rules are encoded via [pydantic](https://docs.pydantic.dev/) models located in
`fair3/engine/validate.py`. The models are versioned alongside the engine and guarantee deterministic
behaviour across platforms.

> **Disclaimer:** strumento informativo/educational; non costituisce consulenza finanziaria o raccomandazione.

