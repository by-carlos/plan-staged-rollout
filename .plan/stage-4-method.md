# S4 — Method (SKILL.md)

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the three new references S0 wrote under `skills/staged-rollout/references/`.

## Goal

`SKILL.md` describes the new steps as method, referencing — not restating — the
new references, so the method and the formats stay one source each.

## Steps

- [x] Describe the requirements step and decision triage in *Decomposing the work*, or a new section if that fits better.
- [x] State depth by size per D-7.
- [x] State the final review stage's new job per D-1.
- [x] Point at `decisions-format.md`, `plan-review.md` and `templates/BRIEF.md` — one link each.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- `SKILL.md` links each new reference exactly once — grep counts into the ledger notes.

## Artifacts

- `skills/staged-rollout/SKILL.md`.
