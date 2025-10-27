# Observability & Telemetry

FAIR-III v0.2 centralises logging and runtime telemetry to make Windows-first CLI
runs debuggable without bespoke infrastructure.

## Structured Logging

- Use `fair3.engine.logging.setup_logger(name, json_format=False, level=None)` in
  every module. The helper reads `FAIR_LOG_LEVEL` (default `INFO`) and attaches a
  console handler automatically.
- When `json_format=True` or `FAIR_JSON_LOGS=1`, the logger also mirrors records
  to `artifacts/audit/fair3.log` as single-line JSON containing
  `timestamp`, `level`, `source`, `message`, `process_time_ms`,
  `bytes_downloaded`, `rows_processed`, and `ratelimit_event`.
- CLI runs expose `--json-logs/--no-json-logs` and call
  `configure_cli_logging()` so all `fair3.*` loggers share the same
  configuration.

## Metrics Stream

Call `record_metrics(metric_name, value, tags=None)` to append numerical gauges
(e.g. rows ingested, bootstrap iterations) to
`artifacts/audit/metrics.jsonl`. Each line captures a UTC timestamp, the metric
name, the float value, and optional string tags. Metrics are safe to call from
multiple commands; the helper ensures the audit directory exists.

## Progress Bars

Ingest fetchers now wrap symbol downloads with `tqdm`, activated via
`--progress` or `--no-progress` on the CLI. The progress bar shows
`ingest:<SOURCE>` with per-symbol updates and automatically disappears when
disabled (default).

## Test Harness Integration

Pytest fixtures rely on the same helpers: the autouse fixture in
`tests/conftest.py` sets `FAIR_LOG_LEVEL=INFO` so unit tests inherit a consistent
verbosity. Individual tests can opt-in to JSON logging by setting
`FAIR_JSON_LOGS=1` or calling `configure_cli_logging(True)`.

## Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| JSON log file missing | `--json-logs` not passed and `FAIR_JSON_LOGS` unset | Run with `fair3 ... --json-logs` or export `FAIR_JSON_LOGS=1`. |
| Progress bar not visible | Running under CI or `--no-progress` | Pass `--progress` explicitly; the flag defaults to `False`. |
| Duplicate log lines | Logger reconfigured without clearing handlers | Rely on `setup_logger` (idempotent) instead of manual handler wiring. |

All paths and filenames are relative to the project root to ease Windows
compatibility and reproducibility.
