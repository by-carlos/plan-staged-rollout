# Cloud fire probe — build ledger

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
| S0 Fire evidence | doing | yes | 2026-09-01 | Evidence recorded: model, effort vars, branch, plugin availability |

## Notes

As-built notes, acceptance evidence, gotchas, handoff notes, follow-ups. One
block per stage; sessions read only the blocks of their `depends` stages.

### S0 Fire evidence

**Acceptance checks:**
- ✓ `probe/cloud-fire-evidence.md` exists on the stage branch
- ✓ Contains all five labelled observations with commands and outputs:
  - Model: claude-haiku-4-5 (from system prompt)
  - CLAUDE_EFFORT: (empty, confirmed via `echo "$CLAUDE_EFFORT"`)
  - CLAUDE_CODE_EFFORT_LEVEL: (empty, confirmed via `echo "$CLAUDE_CODE_EFFORT_LEVEL"`)
  - Starting branch: plan-cloud-fire-probe-s0-wcssqj (pre-stage-creation state)
  - Plugin slash commands: no (cloud container, plugin not loaded)
- ✓ Worktree properly provisioned during preflight (drift correction applied: plan branch in clone, stage branch in worktree)
- ✓ Stage PR opened into plan branch
