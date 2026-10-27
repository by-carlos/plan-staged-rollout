# Estimates, actuals and the usage report

A plan carries a rough time estimate for every stage, records what each stage
really took, and reports the two side by side at closeout. This file is the
method: how the first estimates are made, how they are measured, and how later
plans learn from earlier ones.

**These are guesses, not promises.** An estimate covers the stage's own work
in a session. It leaves out waiting on the user, blockers and unknowns, so a
stage that stops at a gate will run over it.

## The estimate

- **Where it lives.** The stage index's `estimate` column, one cell per stage,
  and nowhere else (stage files never restate it, like every other column).
- **Its form.** A range in hours: `1–2h`, `0.5-1h` (en dash or hyphen), or a
  bare `2h` when there is no spread. `—` means "not estimated" and is reported
  as such, never counted as zero silently.
- **The plan total.** The `Plan estimate:` line under the plan flags, computed,
  never added up by hand:

  ```
  python "${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/scripts/estimates.py" plan --plan-dir .plan
  ```

  It prints two totals. **Summed** is every stage end to end, the session time
  the plan costs. **Elapsed** is the longest `depends` chain, the clock time
  when every wave runs in parallel; it is the floor no amount of parallelism
  removes. With a ledger beside it, the same command prints `remaining_line`:
  what is left once `done` and `skipped` stages drop out.

## The first rule: judged, anchored

Before any actuals exist, the planner judges each stage's range from its
Steps and Artifacts, against these anchors. They are starting values, meant
to be replaced (see *Calibration*).

| A stage that… | Range |
|---|---|
| edits one or two documents, no code | `0.25–0.5h` |
| changes one script or module, with its tests | `0.5–1.5h` |
| adds a component across several files, with tests | `1.5–3h` |
| builds a keystone others depend on, or crosses repos | `2–4h` |
| reviews the plan (`SF`) | `0.5–1h` |

Widen the range rather than raise its middle when a stage is uncertain, and
split a stage whose honest range runs past 4h. The `model` and `effort`
columns do not set the estimate: effort is reasoning depth, not amount of
work.

## Actuals

Each session that works on a stage, whether it finishes, stops `doing` or
stops `blocked`, adds one line to the stage's notes block in `LEDGER.md`:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/scripts/effortlog.py" usage
```

It prints JSON whose `line` is pasted as is:

```
Actuals: 2026-07-08T12:41:09Z → 2026-07-08T15:02:44Z · 142 min · tokens in=212 out=48310 cache_read=6120455 cache_write=301877 · subagents=1
```

- **Source.** The session's own transcript (`<session-id>.jsonl`), the only
  record present in the CLI, the desktop app and cloud sessions alike. Each
  streamed message is counted once; subagents' transcripts are included.
- **Time** is wall clock from the transcript's first entry to its last, so it
  includes time spent waiting on the user.
- **Tokens only.** No dollar cost and no share of a usage limit: cost needs a
  price table that goes stale and means nothing on a subscription, and a
  usage limit is the account's, shared with every other session.
- The fields are raw integers on purpose: `estimates.py report` reads them
  back. A resumed stage has one line per session, and the report sums them.

## The usage report

`/plan-close` prints it and puts it in the final PR body, before `.plan/` is
removed:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/scripts/estimates.py" report --plan-dir .plan
```

Per stage: status, estimate, actual hours, tokens in (cache included), tokens
out and the number of measured sessions. Then the plan's estimate, its
actual summed and elapsed hours, its token totals, and every stage with no
`Actuals:` line, named rather than guessed.

## Calibration

The ledger is deleted at closeout, so what later plans learn from is the
effort log (`CLAUDE_EFFORT_LOG`, opt-in). Each `/stage-run` row carries the
stage's `estimate`, its measured `elapsed_minutes` and its `tokens`.
`/plan-stages` runs, before estimating:

```
python "${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/scripts/estimates.py" calibrate
```

- It takes every `stage-run` row with both an estimate and a measured span,
  divides the actual hours by the estimate's midpoint, and reports the
  **median** ratio as `factor`.
- With fewer than three such rows, or no log, `factor` is null: use the
  anchors as written.
- Otherwise judge the range from the anchors as before, then multiply both
  ends by `factor`, and say so in the bootstrap's announcement ("estimates
  scaled by 1.4 from 12 past stages").
- Once the log is large enough to read by stage kind, replace the anchors'
  ranges here with the observed medians, in a pull request of their own.

A token estimate is not made yet. The log now records tokens per stage, and
one is added the same way once there are enough rows to base it on.
