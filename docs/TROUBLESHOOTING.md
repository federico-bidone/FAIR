# Troubleshooting Guide

This guide will catalogue common operational issues (installation, SSL, fonts, data access) and their remediations. Entries will be added as we validate the pipeline across environments.

## Reporting Layer
- **Matplotlib backend errors on Windows CI** – ensure the optional dependency
  `matplotlib` is installed and the environment honours the Agg backend. The
  reporting module enforces `matplotlib.use("Agg", force=True)` but missing DLLs
  can still occur when system packages are absent. Install the Visual C++
  redistributable or `pip install --upgrade matplotlib`.
- **Empty artefacts under `artifacts/reports/`** – verify the ETL pipeline ran
  for the requested period. The CLI ships with a deterministic synthetic fallback;
  once real PIT artefacts are wired in, missing parquet files will trigger this
  symptom.
- **Large PNG sizes** – plots default to 8x4.5 inches at 150 dpi. Reduce size by
  invoking `generate_monthly_report(..., output_dir=...)` and post-processing
  images, or lowering the DPI before saving.

## Robustness Lab
- **`summary.json` missing or empty** – ensure `run_robustness_lab` received a non-empty
  return series. The bootstrap sampler raises when the iterable is empty; feed
  portfolio returns from the reporting stage or a synthetic placeholder.
- **PDF generation fails** – confirm `matplotlib` is installed and the process
  has write permissions to `artifacts/robustness/`. The lab forces the Agg
  backend but still requires the `matplotlib` package.
- **Ablation runner errors** – the callback must accept a mapping of governance
  flags and return a mapping of metric names to floats. Optionally accept a
  `seed` or `rng` keyword for deterministic sampling.

## Goals Engine
- **"No goals configured" error** – ensure `configs/goals.yml` contains at least
  one goal entry with keys `name`, `W`, `T_years`, `p_min`. The CLI raises if the
  list is empty or malformed.
- **Probabilità fuori range** – verify monthly contributions and horizons are
  realistic. Extremely low contributions relative to targets will naturally
  yield success probabilities vicino a 0.0; adjust `--monthly-contribution` o il
  file `configs/params.yml` per scenari plausibili.
- **PDF non generato** – controllare i permessi di scrittura nella directory
  di output (`--output-dir`). Il motore usa Matplotlib/Agg; installare la
  dipendenza se assente (`pip install matplotlib`).
