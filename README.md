# FAIR-III (Unified) Portfolio Engine

> **Educational only** — This repository provides a research and learning implementation of the FAIR-III portfolio construction framework. It is **not** an investment recommendation, financial promotion, or personalised advice under MiFID II.

## Overview
FAIR-III (Unified) is a Windows-first, Python-only portfolio research stack that ingests free macro and market data (ECB, FRED, BoE, Stooq), builds point-in-time panels, estimates expected returns and covariance matrices, constructs factor-aware allocations with strong retail implementability constraints, and produces auditable execution and reporting artefacts. The system emphasises parsimony, replicability, and compliance with UCITS/EU/IT constraints, including deterministic seeding, audit trails, and realistic cost/tax handling.

### Key Features
- Deterministic, auditable pipeline with central seed management and checksum logging.
- CLI pipelines (`fair3 factors`, `fair3 estimate`, `fair3 optimize`, `fair3 map`) orchestrate
  factor generation through instrument mapping while capturing audit snapshots automatically.
- Ensemble mean/variance estimation with Black–Litterman blending and fallback when information ratios are insufficient.
- Factor allocation generators (Max-Sharpe, HRP, DRO, CVaR-ERC) combined by a meta-learner penalising turnover and tracking error.
- Mapping from factor allocations to instruments with rolling ridge betas, intra-factor HRP, and liquidity/ADV caps.
- Regime overlay using a committee of signals with hysteresis and cool-down controls.
- Execution layer with lot sizing, Almgren–Chriss transaction costs, Italian tax heuristics, and no-trade safeguards.
- Monthly reporting, robustness lab (bootstrap/replay), ablation studies, and comprehensive audit artefacts.
- Goal-based Monte Carlo engine producing regime-aware success probabilities and glidepath artefacts.

## Installation (Windows 11)
1. Install Python 3.11 (64-bit) from the Microsoft Store or python.org and ensure `python` points to 3.11.
2. Open **PowerShell** and set the execution policy if needed: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`.
3. Clone the repository and create a virtual environment:
   ```powershell
   python -m venv .venv
   . .venv/Scripts/Activate.ps1
   pip install -e .[dev]
   pre-commit install
   ```
4. Confirm the setup:
   ```powershell
   ruff check .
   ruff format --check .
   black --check .
   pytest -q
   ```

## Quickstart Pipeline
Run the CLI end-to-end on a machine with internet access for data downloads. Each command logs activity under `artifacts/` and audit metadata under `artifacts/audit/`.

```powershell
fair3 ingest --source ecb --from 1999-01-04
fair3 ingest --source fred --symbols DGS10 DCOILWTICO
fair3 ingest --source boe  --from 1980-01-01
fair3 ingest --source stooq --symbols spx usdeur.v

fair3 etl --rebuild
fair3 factors --validate --oos-splits 5
fair3 estimate --cv-splits 5
fair3 optimize --generators A,B,C --meta
fair3 map --hrp-intra --adv-cap 0.05
fair3 execute --rebalance-date 2025-10-20 --dry-run
fair3 report --period 2025-01:2025-10 --monthly
fair3 goals --draws 12000 --seed 21 --output-dir artifacts/goals_demo
```

`fair3 factors` now writes deterministic factor panels (`artifacts/factors/*.parquet`),
validation diagnostics, and metadata (including economic sign governance). `fair3 estimate`
produces consensus `mu_post.csv`, `sigma.npy`, and blend/drift logs under
`artifacts/estimates/` while copying configuration and seed snapshots into
`artifacts/audit/`. `fair3 optimize` stores generator-specific CSVs, the blended allocation,
and ERC diagnostics inside `artifacts/weights/`. `fair3 map` translates factor weights to
instrument exposures with rolling betas, CI80 bands, tracking-error summaries, and liquidity
adjustments persisted under `artifacts/mapping/` and `artifacts/weights/`.

To stress test the latest allocations, invoke the robustness lab (temporary script until a CLI subcommand lands):

```powershell
python - <<'PY'
from pathlib import Path
import pandas as pd
from fair3.engine.robustness import RobustnessConfig, run_robustness_lab

returns = pd.Series([0.001] * 252)  # replace with portfolio returns
run_robustness_lab(returns, config=RobustnessConfig(draws=256, block_size=60), seed=42)
PY
```

`fair3 execute` currently surfaces the deterministic decision breakdown (drift,
expected benefit, cost, tax) without submitting orders. `fair3 report --period
... --monthly` emits deterministic CSV/JSON summaries and PNG plots inside
`artifacts/reports/<period>/`; synthetic fixtures back the CLI until the full
pipeline wires real PIT artefacts through the reporting layer. `fair3 goals`
reads `configs/goals.yml`/`configs/params.yml`, runs a regime-aware Monte Carlo
simulation, and writes `summary.csv`, `glidepath.csv`, e un PDF in
`artifacts/goals_demo/goals/` (o directory custom) per auditare le probabilità
di successo.

## Data Sources & Licensing
| Source | Coverage | Notes |
| --- | --- | --- |
| ECB | Euro area rates, macro | Uses SDW REST CSV endpoint with logged license/URL per request. |
| FRED | US macro/market | Public CSV interface (`fredgraph.csv`) without API key; missing data coerced to NaN. |
| Bank of England | Rates, balance sheet | CSV download interface (`_iadb-getTDDownloadCSV`) with attribution logged. |
| Stooq | Market indices, FX | Daily CSV feed (`q/d/l`) respecting personal-use policy. |

Ogni esecuzione di `fair3 ingest` produce file CSV timestampati (`<source>_YYYYMMDDTHHMMSSZ.csv`) con colonne standard (`date`, `value`, `symbol`) salvati in `data/raw/<source>/`. Le informazioni di licenza e gli URL vengono registrati nei log rotanti sotto `artifacts/audit/` per supportare la conformità UCITS/EU/IT. Il passo ETL ricostruisce un pannello PIT salvando `prices.parquet`, `returns.parquet`, `features.parquet` in `data/clean/` e il QA log in `audit/qa_data_log.csv`. Do not redistribute third-party datasets without permission.

## Core Concepts
- **μ/Σ estimation:** Expected returns come from a shrink-to-zero + bagging OLS + gradient boosting ensemble stacked via ridge and blended with Black–Litterman equilibrium views (ω:=1 fallback when IR<τ). Covariances are blended (Ledoit–Wolf, graphical lasso, factor shrinkage, element-wise mediana) and projected to PSD via Higham (2002).
- **Σ drift guards:** Relative Frobenius and max-correlation diagnostics trigger acceptance gates and execution overlays when structural breaks emerge.
- **Black–Litterman fallback:** Views blend with equilibrium unless the view information ratio drops below `τ_IR=0.15`, in which case the system reverts to market equilibrium (ω=1).
- **Higham PSD projection:** Ensures covariance matrices remain positive semi-definite before optimisation.
- **Hierarchical Risk Parity (HRP):** Provides diversified baseline allocations and intra-factor distribution.
- **CVaR / EDaR:** Tail-risk constraints and objectives expressed in monthly (CVaR 95%) and three-year (EDaR) horizons.
- **Distributionally Robust Optimisation (DRO):** Penalises allocations by Wasserstein radius ρ to guard against estimation error.
- **Macro factor stack:** Ten deterministic macro premia (market, momentum, reversal, value, carry, quality, defensive, liquidity, growth, inflation, rates) produced via quantile spreads with CP-CV/DSR/FDR validation and orthogonality guards.
- **Regime tilt:** A committee (two-state Gaussian HMM, volatility stress, macro slowdown) produces crisis probabilities that drive a tilt parameter λ with hysteresis (on=0.65, off=0.45, dwell=20 days, cooldown=10 days).
- **Factor-to-instrument mapping:** Rolling ridge betas with bootstrap caps feed intra-factor HRP, tracking-error budgets, and ADV-aware trade sizing.
- **Liquidity & Compliance:** Tracking-error budgets, turnover caps, and ADV/lot size constraints ensure retail implementability.
- **No-trade rule:** Trades execute only when drift bands are breached **and** expected benefit minus costs and taxes remains positive.
- **Monthly reporting:** Aggregates PIT artefacts into compliance-ready CSV/JSON summaries, factor/instrument attribution, turnover/cost dashboards, and fan charts stored under `artifacts/reports/<period>/`.
- **Robustness lab & ablation:** Block bootstraps (60-day) and stylised shocks (1973, 2008, 2020, stagflation) assess acceptance gates; governance toggles run via ablation harness to document the lift of PSD, BL fallback, drift triggers, meta TO/TE, regime tilt, and the no-trade rule.
- **Goal-based planning:** Monte Carlo simulation blends base/crisis regimes with deterministic glidepaths and contribution schedules, emitting weighted success probabilities and PDF dashboards under `artifacts/goals/`.

## Repository Layout
```
pyproject.toml
README.md
LICENSE
PLAN.md
.pre-commit-config.yaml
.ruff.toml
.github/
  workflows/ci.yml
  ISSUE_TEMPLATE/
  PULL_REQUEST_TEMPLATE.md
CODEOWNERS
SECURITY.md
CONTRIBUTING.md
docs/
configs/
data/
artifacts/
fair3/
  cli/main.py
  engine/
    ingest/
    etl/
    factors/
    estimates/
    allocators/
    mapping/
    regime/
    execution/
    goals/
    reporting/
    robustness/
    utils/
tests/
```
Each engine submodule will ship with its own README detailing APIs, CLI usage, common errors, and tracing flags as functionality lands in later milestones.

## Troubleshooting (Windows)
- **Build tools:** Install the "Desktop development with C++" workload (Visual Studio Build Tools) if `cvxpy` requires compilation.
- **SSL errors:** Update Windows certificates or install `pip install certifi`. Set `SSL_CERT_FILE` to the certifi bundle if needed.
- **Matplotlib fonts:** Run `python -c "import matplotlib.pyplot as plt"` once to trigger font cache creation. Delete `%USERPROFILE%\.matplotlib` if corrupted.
- **Long paths:** Enable long path support via `reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f` (requires admin).

## FAQ
**Why enforce PSD covariances?** Optimisers require PSD matrices to avoid arbitrageable negative variances and ensure stable solutions.

**Why use HRP as a baseline?** HRP provides diversified allocations with low turnover and serves as a robust benchmark for acceptance gates.

**How are Italian taxes simplified?** Capital gains taxed at 26%, qualifying government securities pro-rated at 12.5%, stamp duty 0.2%, losses tracked for four years. Consult a professional for real portfolios.

**How is look-ahead bias avoided?** The ETL builds point-in-time panels with lagged features and embargoed cross-validation folds.

**Why so many audit artefacts?** Seeds, config snapshots, and checksums enable reproducibility and regulatory-grade tracing.

## License
This project is released under the Apache 2.0 License (see `LICENSE`).
