# S2 — Runners respect `live`

Issue: by-carlos/plan-staged-rollout#227

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read S0's ledger notes and the `live` definition it wrote in the
> PLAN.md template; D-3 is the decision this stage implements.

## Goal

Make every runner honour `gate: live`: the session-start hook, the RUNNER.md
template, the two commands that start stages, and the remote driver. A driver
fires a stage only when its gate is `auto` or absent, so it never fires a `live`
stage; `/stage-run` refuses to start a second `live` stage at once (D-3). S5
builds on the shared driver text.

## Steps

- [ ] `commands/stage-run.md`: add the start-time refusal. In preflight, reuse
  preflight 0.5's live-sibling signature (another stage's `todo` row with a
  stage branch that has commits, or a worktree for another `todo`/`doing`
  stage): if that other stage is `live` and this one is `live`, refuse to start
  and name the sibling. Also refuse an unattended `live` stage.
- [ ] `hooks/session-start`: parse `gate`; when two or more `live` stages are
  runnable, list them and note that only one may run at a time (the refusal
  itself is `/stage-run`'s); keep parsing legacy suffixed IDs.
- [ ] Add `live` to every place that names the refused values, so no runner is
  left denying only `human` and `local`:
  - `commands/plan-run.md`: the lead note on skipped gates; step 3 (see the next
    item); step 5 (the gate branches: fire only on `auto` or absent, refuse and
    name any other value, `live` and unknown ones included); step 7 (the
    "nothing fired" loop exit); step 8 (the skipped-stages line of the end
    announcement).
  - `skills/staged-rollout/references/remote-driver.md`: the refusal list
    ("`gate: human` and `gate: local` stages are never fired"), and its
    firing rule (fire only on `auto` or absent). Do not add a separate "never
    two `live`" item; the `/stage-run` refusal replaces it.
  - `skills/staged-rollout/references/templates/RUNNER.md`: section 4
    ("Refuse a `gate: human` or `gate: local` stage"), so it refuses `live`
    and any unknown value too.
- [ ] `commands/plan-run.md` step 3: a plan whose `.plan/RUNNER.md` predates
  this change is refreshed by the existing refresh rule (RUNNER.md's header:
  regenerate it from the plugin template, never edit the two out of step),
  not left stale; the step today only back-fills a missing file.
- [ ] Add a fixture plan under
  `skills/staged-rollout/tests/fixtures/live-plan/.plan/` with build and live
  stages, including one row with an unknown gate value.
- [ ] Run the hook against the fixture and paste what it prints. Copy the
  fixture to a scratch directory, `git init` there and run the hook from it;
  the hook resolves the plan root with `git rev-parse --show-toplevel`, so
  running it inside this repository would read this repository's `.plan/`.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- Run the hook from the scratch copy of the fixture (see the last Step) and
  paste the context it prints: it shows the right runnable stages, the
  one-live-at-a-time note, and the unknown-gate row as refused and named.
- A grep over `commands/`, `hooks/` and `skills/staged-rollout/` shows no
  runner that still denies only `human`/`local`; paste the grep and its output.
- `python3 scripts/validate_plugin.py` passes.

## Artifacts

- `hooks/session-start`
- `skills/staged-rollout/references/templates/RUNNER.md`
- `commands/stage-run.md`
- `commands/plan-run.md`
- `skills/staged-rollout/references/remote-driver.md`
- `skills/staged-rollout/tests/fixtures/live-plan/.plan/` (fixture plan: index, ledger and stage files)

## Notes

- Depends on S0: consumes its definition of `live` (never fired by a driver,
  never two at once).
- S5 shares `plan-run.md` and `remote-driver.md` with this stage and reads
  what it wrote there.
- PLAN.md › Requirements › Done carries the same fixture procedure (scratch
  copy, `git init`, hook run from there); keep the two in step if it changes.
