# Robustness Module

The robustness package stress-tests FAIR-III allocations using deterministic
block bootstraps, stylised historical shocks, and governance ablations. Outputs
feed the acceptance gates that guard retail suitability.

## Public API

### `fair3.engine.robustness.bootstrap`
- `block_bootstrap_metrics(returns, block_size=60, draws=1000, periods_per_year=252, ...)`
- `RobustnessGates`

### `fair3.engine.robustness.scenarios`
- `ShockScenario`
- `default_shock_scenarios()`
- `replay_shocks(base_returns, scenarios=None, scale_to_base_vol=True, periods_per_year=252)`

### `fair3.engine.robustness.ablation`
- `DEFAULT_FEATURES`
- `run_ablation_study(runner, features=None, base_flags=None)`
- `AblationOutcome`

### `fair3.engine.robustness.lab`
- `RobustnessConfig`
- `RobustnessArtifacts`
- `run_robustness_lab(returns, config=None, seed=None, scenarios=None, ablation_runner=None, base_flags=None)`

## CLI / Pipeline Usage

The orchestration layer will call `run_robustness_lab` after monthly reporting to
produce CSV diagnostics and a compact PDF in `artifacts/robustness/`. Pass an
`ablation_runner` callback that toggles features (e.g., BL fallback, PSD
projection) and returns metrics such as Sharpe, TE, or drawdown.

```python
from fair3.engine.robustness import RobustnessConfig, run_robustness_lab

def evaluate(flags):
    # Invoke downstream pipeline with the provided governance flags.
    return {"sharpe": 0.85, "max_drawdown": -0.22}

artifacts, gates = run_robustness_lab(
    returns=portfolio_returns,
    config=RobustnessConfig(draws=256, block_size=60),
    seed=42,
    ablation_runner=evaluate,
)
print("Gates satisfied:", gates.passes())
```

## Common Errors & Troubleshooting

| Symptom | Likely Cause | Resolution |
| --- | --- | --- |
| ValueError about block size | Requested block size larger than data sample | Use the available length or pass aggregated returns |
| Empty ablation table | Callback returned no metrics | Ensure the ablation runner maps flags to metric dicts |
| Missing PDF outputs | Matplotlib backend not available | The module enforces `Agg`; install matplotlib on the target machine |

## Trace Hooks

Supply a deterministic `seed` or rely on `audit/seeds.yml` so bootstrap and
scenario outputs are reproducible. Downstream orchestration should log the
returned artefact paths via `fair3.engine.utils.log.get_logger` when `--trace`
flags are active.
