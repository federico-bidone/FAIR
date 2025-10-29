# CLI architecture

> Strumento informativo/educational; non costituisce consulenza finanziaria o raccomandazione.

The CLI module centralises argparse plumbing for every FAIR-III subcommand.
New commands must remain additive and backwards compatible with v0.1, respect
`--dry-run`, `--progress/--no-progress`, and `--json-logs/--no-json-logs`, and
use the typed helper functions defined in the engines.

## Adding a command
1. Implement an engine function with full docstring coverage and deterministic
   behaviour.
2. Extend the `_add_<feature>_subparser` helper with descriptive `help` strings
   and examples.
3. Wire the handler inside the dispatcher at the bottom of `main.py` and ensure
   CLI integration tests cover the new entrypoint.

## Testing checklist
- Add unit tests for argument parsing (use `pytest` and `CliRunner` when
  appropriate).
- Confirm `pytest -q` and pre-commit hooks remain green on Windows 11.
- Update `docs/` guides and the main README with usage examples and licensing
  nuances when the command touches external data.
