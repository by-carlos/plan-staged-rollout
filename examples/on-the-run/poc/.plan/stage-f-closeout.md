# SF — Closeout

The standing final stage. It **never implements** — it verifies, records, and
catalogs loose ends. Depends on S1 and S2; reads every notes block.

## Steps

- [ ] Capture each stage's pull-request state into `.plan/pr-states.json`
      using the GitHub MCP server (`mcp__github__pull_request_read`) — there
      is no `gh` in a routine run. One object per stage id:
      `{"S0": {"number": 1, "state": "closed", "merged": true, "base": "plan-slugify"}, ...}`.
      Do not hand-write a state you have not read back from GitHub.
- [ ] Run the verification script and capture its full output:
      `python3 scripts/verify_run.py --repo .`
- [ ] Paste that output into this stage's ledger notes block as the run's
      evidence, and state the exit status explicitly.
- [ ] If it fails, mark this row `blocked` and write `.plan/BLOCKED.md` naming
      the failing checks. Do **not** fix the underlying stages from here — a
      closeout that repairs its own subject proves nothing.
- [ ] Catalog loose ends: each becomes a follow-up issue, a spin-off
      candidate, or an explicit "accepted, won't fix". Record findings about
      the stage-runner or orchestrator contracts as notes to route back to
      their own issues — never edit those contracts from inside this run.
- [ ] Open this stage's pull request into the plan branch and, under
      `merge: auto`, squash-merge it once green.
- [ ] **Open the `plan-slugify` → `main` pull request** and leave it open. Say
      in its body that it must be merged as a **normal, non-squash** merge, and
      summarise the stage table and the verification result. Opening it is
      compulsory and is the last thing this stage does; merging it is not
      yours.

## Acceptance

- [ ] `python3 scripts/verify_run.py --repo .` exits `0`, with its output
      pasted into the ledger notes block.

## What SF does NOT do

**Merge** the `plan-slugify` → `main` pull request. Opening it is this stage's
job (above); merging it is the maintainer's, by hand, after reading this
stage's evidence — a fixed condition of the proof of concept.

The distinction is the whole gate: a closeout that cannot open the final PR
leaves the maintainer doing clerical work the run should have done, while a
closeout that merges it removes the one decision the run exists to preserve.
Open it, describe it, stop.
