# S4 — Bootstrap: programmes, waits, ordering

Issue: by-carlos/plan-staged-rollout#227

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read S0's ledger notes and the `live` and numbering rules it wrote;
> D-1, D-2, D-6, D-7, D-9 and D-11 are the decisions this stage implements.

## Goal

Teach the bootstrap and closeout commands about programmes, day-long waits and
stage ordering: propose a programme per D-1, keep `PROGRAMME.md` per D-6,
refuse day-long waits as stages per D-7, and number stages in running order
with no suffixed IDs. S5 builds its "later plan" outcome and its wait handling
on this.

## Steps

- [ ] `commands/plan-stages.md`: propose a programme per D-1; refuse a wait
  measured in days as a stage per D-7; number stages in running order with
  parallel stages consecutive; reject suffixed IDs; make the group-by-gate rule
  cover `live`; add a step that creates `PROGRAMME.md` at the repository root
  when a programme is accepted.
- [ ] `commands/plan-close.md`: remove this plan's line from `PROGRAMME.md` (the last plan removes the file) per D-6 and offer to plan
  the next plan.
- [ ] `SKILL.md` › *Decomposing the work* and *Closeout* sections only: the
  same rules.
- [ ] Add the programme index format as
  `skills/staged-rollout/references/programme-format.md`. It lives outside
  `templates/` on purpose: the bootstrap copies `templates/*.md` into every
  plan, and the programme index belongs at the repository root, not in a plan.
- [ ] Check `scripts/validate_plugin.py`: `TEMPLATE_FILES` lists the files
  expected in `templates/`; because the new file is not a template, the list
  stays as is. Confirm that, and name any change in the ledger notes if the
  validator turns out to need one.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- The edited text is quoted in the ledger notes: the `/plan-stages` programme
  proposal, the wait refusal, the running-order numbering rule and the
  `PROGRAMME.md` creation step.

## Artifacts

- `commands/plan-stages.md`
- `commands/plan-close.md`
- `skills/staged-rollout/SKILL.md` (*Decomposing the work* and *Closeout* sections only)
- `skills/staged-rollout/references/programme-format.md` (new)
- `scripts/validate_plugin.py` (only if the check above shows it must change)

## Notes

- Depends on S0: consumes its `live` definition (for group-by-gate) and its
  numbering rules (running order, no suffixed IDs).
- S5 consumes the programme index (the "later plan" outcome) and the wait
  refusal (dated follow-ups).
- S6 edits SKILL.md › *Decomposing the work* later, for stage-size guidance
  only; the two stages are in different waves.
