# S1 — CLI runner

<!-- This stage's flags (depends / mode / exec / model / effort) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.

## Goal

A console entry point `uptime-page` that loads the config, runs the checks,
prints a per-check summary line, and exits with a meaningful code — the piece
a cron job or CI schedule invokes.

## Steps

- [x] Argparse skeleton: `uptime-page [--config PATH]`, `--help` text, wired
  as a console script in `pyproject.toml`.
- [x] Dispatch to `run_checks` and print one summary line per check
  (`OK`/`FAIL`, status, latency).
- [ ] `--config` path override; catch `ConfigError` and print a friendly
  one-line message instead of a traceback.
- [ ] Exit codes: 0 all checks pass, 1 any check failed, 2 config error —
  with a test for each in `tests/test_cli.py`.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `uptime-page --config checks.toml; echo $?` prints one line per configured
  check and exits `0` when all checks pass.
- `python -m pytest tests/test_cli.py -q` passes.

## Artifacts

`uptime/cli.py`, `tests/test_cli.py`, the `[project.scripts]` entry in
`pyproject.toml`. No secrets involved.
