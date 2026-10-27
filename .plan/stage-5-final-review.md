# S5 — Final review that stays last

Issue: by-carlos/plan-staged-rollout#227

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the ledger notes of S2, S3 and S4; D-4 and D-7 are the decisions
> this stage implements.

## Goal

Make the final review stay last: its outcomes become issue, later plan or
accepted, plus a capped, user-approved fix (D-4); day-long waits become dated
follow-ups (D-7); documentation is written only on a clean pass; unattended,
SF stops and asks on a fix.

## Steps

- [x] `stage-f-review.md` template: outcomes per D-4; dated follow-ups per D-7;
  docs written only on a clean pass; the fix exception with its limits (names
  what it repairs, user present and yes, `Fix: …` titles, a `#### Fixes` list
  in SF's ledger notes, at most 3 with a fourth a hard stop in every mode, own
  verification); how a fix runs per D-4 (SF's PR lands the `Fix:` row before
  SF, extends SF's `depends` to it and sets SF back to `todo`; the fix runs,
  then SF re-runs from the top as a redo; unattended, SF records a block
  instead); a dated follow-up's body states the date, exact check, pass
  condition and action on failure (D-7). Remove the "New stage in this plan"
  outcome.
- [x] `SKILL.md` › *The final review stage* section only: the same rules.
- [x] PLAN.md template: rewrite the "Final review stage" frozen-decision line.
- [x] `commands/plan-run.md` and `remote-driver.md`: an unattended SF stops and
  asks on a fix.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- The edited text is quoted in the ledger notes: the template's outcomes, the
  fix exception with its limits, and the unattended-stop lines.
- `grep` shows no remaining "New stage in this plan" outcome.

## Artifacts

- `skills/staged-rollout/references/templates/stage-f-review.md`
- `skills/staged-rollout/SKILL.md` (*The final review stage* section only)
- `skills/staged-rollout/references/templates/PLAN.md` (the "Final review stage" frozen-decision line)
- `commands/plan-run.md`
- `skills/staged-rollout/references/remote-driver.md`

## Notes

- Depends on S2, S3 and S4: consumes S3's script (fix insertion), S4's
  programme index (the "later plan" outcome) and wait refusal (dated
  follow-ups), and S2's driver text (`plan-run.md` and `remote-driver.md` are
  shared files; read what S2 wrote before editing).
- This plan's own `.plan/stage-f-review.md` is not an Artifact here: its copy
  was fixed at bootstrap. This stage edits the template only.
- S6 documents the result.
