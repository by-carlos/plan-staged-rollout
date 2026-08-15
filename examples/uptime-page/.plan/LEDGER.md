# Uptime page — build ledger

Statuses: `todo → doing → done`, plus `blocked` (waiting on a human or an
external gate — the stage becomes a runbook) and `skipped` (decided against,
one-line reason). Partial completion is a normal, resumable state.

Keep table rows to **ONE line** — detail goes in the notes block below, never
in a table cell. Sessions read the status table plus only the notes blocks of
the stages they `depend` on (the final review stage reads all of it). Update
your stage's row and notes block at the end of every session (Operating
protocol, finish protocol).

## Status

| Stage | Status | Verified | Date | Result |
|---|---|---|---|---|
| S0 Checker core | done | yes | 2026-07-08 | Checker + config parsing landed; PR #1 squash-merged |
| S1 CLI runner | doing | — | 2026-07-10 | Args + dispatch done; `--config` override and exit codes left (see notes) |
| S2 Status page | todo | — | — | — |
| SF Plan review | todo | — | — | — |

## Notes

As-built notes, acceptance evidence, gotchas, handoff notes, follow-ups. One
block per stage; sessions read only the blocks of their `depends` stages.

### S0 Checker core

Acceptance evidence (2026-07-08, on `plan-uptime-page-s0`):

```
$ python -m pytest tests/test_checker.py -q
........                                                                 [100%]
8 passed in 0.41s

$ python -c "from uptime.checker import load_config, run_checks; print(run_checks(load_config('checks.toml')))"
[CheckResult(name='example', url='https://example.com/', ok=True, status=200, latency_ms=131, checked_at='2026-07-08T14:52:07Z')]
```

As-built: `CheckResult` is a frozen dataclass; `load_config` validates every
`[[check]]` entry and raises `ConfigError` naming the offending key.

Gotcha for S1/S2: per the frozen no-raise decision, `run_checks` returns
`ok=False, status=None` on network errors — consumers must branch on the
result, never wrap the call in try/except for flow control.

PR #1 squash-merged into `plan-uptime-page` on 2026-07-08; this row was
flipped to `done` on the plan branch after the merge (finish step 5).

### S1 CLI runner

Handoff (2026-07-10, stopped mid-stage on `plan-uptime-page-s1`): steps 1–2
done and committed (`feat(cli): argparse skeleton and dispatch to run_checks`) —
`uptime-page` runs the checks and prints one summary line per check. Left:
step 3 (`--config` path override + friendly `ConfigError` message) and step 4
(exit codes 0/1/2) plus their tests. Resume from the first unticked box in
`stage-1-cli.md`. No surprises so far — S0's no-raise contract (see S0 notes)
held.

### S2 Status page
_(empty)_

<!-- One ### S<N> block per stage. Templates for the states you'll hit:

  done      — paste the real acceptance output, then the as-built summary and
              any gotchas the next stage needs to know.
  doing     — tick the completed Steps checkboxes in the stage file; write a
              handoff note here (what's left, where to resume).
  blocked   — record exactly what human/external action unblocks it, as a
              runbook the human can follow; no faked progress.
  skipped   — one-line reason.
  follow-up — a shortcut or scope-creep item spotted here that became (or
              should become) its own stage; name it so the review stage sees it.
-->

### SF Plan review
_(empty)_
