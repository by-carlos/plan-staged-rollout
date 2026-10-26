# S2 — Runner and preflight

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the formats S0 wrote under `skills/staged-rollout/references/`.

## Goal

Every stage, cloud sessions included, sees a fresh brief and the `DECISIONS.md`
entries for its files — through `RUNNER.md` and the repo, since the plugin does
not load in the cloud.

## Steps

- [x] Edit the operating protocol / preflight in `skills/staged-rollout/references/templates/PLAN.md` only: the brief stamp check with regenerate-on-mismatch (D-2).
- [x] Add the same two steps to `skills/staged-rollout/references/templates/RUNNER.md`: the stamp check (D-2) and showing the `DECISIONS.md` entries whose paths overlap the stage file's `## Artifacts` (D-1).
- [x] Mirror both steps in `skills/staged-rollout/references/templates/README.md` and `commands/stage-run.md`, recording the target-path convention from D-6.
- [x] Confirm a plan with no `DECISIONS.md` behaves exactly as before.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- `RUNNER.md` and `stage-run.md` describe the same two steps — diff the wording into the ledger notes.
- A plan with no `DECISIONS.md` behaves as before — state the check that shows it.

## Artifacts

- `skills/staged-rollout/references/templates/PLAN.md` (operating protocol / preflight only).
- `skills/staged-rollout/references/templates/RUNNER.md`.
- `skills/staged-rollout/references/templates/README.md`.
- `commands/stage-run.md`.
