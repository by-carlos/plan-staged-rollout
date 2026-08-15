# S<N> — <Stage name>

<!-- This stage's flags (depends / mode / exec / model / effort) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> <List any extra docs to read for THIS stage, or delete this line.>

## Goal

<One or two sentences: what this stage produces and why the plan needs it.
State the outcome, not the steps.>

## Steps

- [ ] <First concrete step.>
- [ ] <Next step.>
- [ ] <...>

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

<Checks that prove the stage is done. Each must produce **pasteable evidence**
(a command + its real output, a query result, a screenshot path) that lands in
the ledger notes — "done" means the check ran, not that the model said so.>

- <Check 1 — e.g. `<command>` shows <expected result>.>
- <Check 2.>

## Artifacts

<The files/config/state this stage creates or changes. Note any secrets that
must NOT be committed.>
