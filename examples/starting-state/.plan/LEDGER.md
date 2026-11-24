# Invoice tool CSV export — build ledger

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
| S0 Export model | done | yes | 2026-11-02 | Export model landed; starting state recorded (1 pre-existing failure); PR #12 squash-merged |
| S1 CSV writer | done | yes | 2026-11-03 | CSV writer landed; only the pre-existing failure remains; PR #13 squash-merged |
| S2 CLI flag | done | yes | 2026-11-04 | `--format csv` landed; only the pre-existing failure remains; PR #14 squash-merged |
| SF Plan review | todo | — | — | — |

## Notes

As-built notes, acceptance evidence, gotchas, handoff notes, follow-ups. One
block per stage; sessions read only the blocks of their `depends` stages.

### S0 Export model

#### Starting state

Commit: `4f9c2a1` (`origin/plan-csv-export` when S0's worktree was cut, before
any change)

- `python -m pytest -q` — fail

  ```
  FAILED tests/test_dates.py::test_due_date_across_dst - AssertionError: assert datetime.date(2026, 3, 30) == datetime.date(2026, 3, 29)
  1 failed, 46 passed in 1.12s
  ```

- `ruff check .` — pass

  ```
  All checks passed!
  ```

- `python -m pytest -m integration -q` — skip: needs the `INVOICE_DB_URL`
  database, which this environment does not have

  ```
  SKIPPED [3] tests/integration/conftest.py:9: INVOICE_DB_URL not set
  3 skipped in 0.08s
  ```

Not fixed here, per the stage's step: the DST failure is in due-date code this
plan does not touch. It became follow-up #9 rather than a stage.

Acceptance evidence (2026-11-02, on `plan-csv-export-s0`):

```
$ python -m pytest -q
FAILED tests/test_dates.py::test_due_date_across_dst - AssertionError: assert datetime.date(2026, 3, 30) == datetime.date(2026, 3, 29)
1 failed, 52 passed in 1.19s

$ ruff check .
All checks passed!
```

Compared with the starting state: `test_due_date_across_dst` failed the same
way there — pre-existing (starting state), not counted against S0. The six new
tests in `tests/test_export_model.py` pass.

As-built: `ExportRow` is a frozen dataclass built by `rows_for(invoices)`;
amounts stay `Decimal` until the writer formats them.

Actuals: 2026-11-02T09:14:02Z → 2026-11-02T10:31:40Z · 78 min · tokens in=188 out=31207 cache_read=3904112 cache_write=211450 · subagents=0

Artifacts check: match

### S1 CSV writer

Acceptance evidence (2026-11-03, on `plan-csv-export-s1`):

```
$ python -m pytest -q
FAILED tests/test_dates.py::test_due_date_across_dst - AssertionError: assert datetime.date(2026, 3, 30) == datetime.date(2026, 3, 29)
1 failed, 60 passed in 1.24s

$ ruff check .
All checks passed!
```

Compared with the starting state: the one failure is
`test_due_date_across_dst`, same assertion — pre-existing (starting state),
not counted against S1. Everything that passed there still passes.

Actuals: 2026-11-03T13:02:51Z → 2026-11-03T13:49:10Z · 46 min · tokens in=97 out=18840 cache_read=2210385 cache_write=140226 · subagents=0

Artifacts check: match

### S2 CLI flag

Acceptance evidence (2026-11-04, on `plan-csv-export-s2`):

```
$ python -m pytest -q
FAILED tests/test_dates.py::test_due_date_across_dst - AssertionError: assert datetime.date(2026, 3, 30) == datetime.date(2026, 3, 29)
1 failed, 64 passed in 1.31s

$ ruff check .
All checks passed!

$ invoice export --format csv --month 2026-10 | head -2
number,customer,issued,due,total
INV-0412,Example Co,2026-10-03,2026-11-02,1250.00
```

Compared with the starting state: pre-existing (starting state) only —
`test_due_date_across_dst`, unchanged. A first run had a second failure,
`tests/test_cli.py::test_unknown_format_exits_2`, which passed in the starting
state, so it counted against S2 and was fixed before the stage finished.

Actuals: 2026-11-04T10:20:33Z → 2026-11-04T11:12:05Z · 52 min · tokens in=121 out=22416 cache_read=2650907 cache_write=158301 · subagents=0

Artifacts check: match

### SF Plan review
_(empty)_
