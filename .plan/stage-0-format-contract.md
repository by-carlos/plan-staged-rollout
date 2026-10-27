# S0 — Format contract: `gate: live` and plain stage IDs

Issue: by-carlos/plan-staged-rollout#227

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the files named under Artifacts below; D-3 and D-9 are the
> decisions this stage writes down.

## Goal

Write the contract the other stages implement: the `live` gate value (D-3) and
the stage-ID and numbering rule (D-9). S2, S3 and S4 consume these definitions;
nothing else in the plan can start without them.

## Steps

- [ ] In the PLAN.md template, add `live` to the flag values: its meaning, that
  a driver never fires it, that runners fire a stage only when its gate is
  `auto` or absent (any other value, unknown ones included, is refused and
  named), and that two `live` stages never run at once (a start-time refusal in
  `/stage-run` preflight, per D-3).
- [ ] In the PLAN.md template, state the stage-ID rule: plain numbers plus
  `SF`; suffixed IDs are read but never created; numbering follows running
  order.
- [ ] In SKILL.md › *Flag heuristics*, extend the `gate` bullet with `live`.
- [ ] In SKILL.md › *Parallel stages*, state that no two `live` stages run at
  once, and add one sentence on the ID rule.
- [ ] Add `live` to the other `gate` consumers: in SKILL.md › *Unattended mode*,
  the hard-stop table rows and the "never launched" sentence; in SKILL.md ›
  *Statuses and human-gated stages*; and in
  `skills/staged-rollout/references/templates/BRIEF.md`, the stage-map gate
  label.
- [ ] Run the acceptance checks and paste the output into the ledger notes.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- `grep -n "live"` on `skills/staged-rollout/references/templates/PLAN.md`,
  `skills/staged-rollout/references/templates/BRIEF.md` and
  `skills/staged-rollout/SKILL.md` shows the new rule in each place the Steps
  name.
- The existing "absent gate column reads as auto" sentence still holds.

## Artifacts

- `skills/staged-rollout/references/templates/PLAN.md`
- `skills/staged-rollout/references/templates/BRIEF.md` (stage-map gate label only)
- `skills/staged-rollout/SKILL.md` (*Flag heuristics*, *Parallel stages*, *Unattended mode*, *Statuses and human-gated stages*)

## Notes

- Depends on nothing. S2, S3 and S4 each consume what this stage defines: S2
  the `live` definition, S3 the ID and numbering rules, S4 both.
- `SKILL.md` is shared with S4, S5 and S6, each in different sections; this
  stage touches only the four sections named above.
- Keeping the format contract in its own wave-0 stage is deliberate: it stops
  three wave-1 stages from writing SKILL.md and the PLAN.md template in the
  same wave.
