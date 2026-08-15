# S0 — Checker core

<!-- This stage's flags (depends / mode / exec / model / effort) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.

## Goal

Produce the core check engine everything else calls: config loading from
`checks.toml` and `run_checks()` returning structured results. S1 (CLI) and
S2 (renderer) are thin consumers of this module — it is the keystone.

## Steps

- [x] Define `CheckResult` (frozen dataclass: `name`, `url`, `ok`, `status`,
  `latency_ms`, `checked_at`).
- [x] Implement `load_config(path)` with `tomllib` + validation (`ConfigError`
  naming the offending key on bad entries).
- [x] Implement `run_checks(config)` with `urllib.request`: per-check timeout,
  honoring the frozen no-raise decision for failing checks.
- [x] Tests: config validation cases + checker behavior with a stubbed opener
  (no real network in tests).

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python -m pytest tests/test_checker.py -q` passes.
- `python -c "from uptime.checker import load_config, run_checks; print(run_checks(load_config('checks.toml')))"`
  prints one `CheckResult` per configured check.

## Artifacts

`uptime/checker.py`, `checks.toml` (sample config with one check),
`tests/test_checker.py`, `pyproject.toml` (package skeleton, no runtime
deps). No secrets involved.
