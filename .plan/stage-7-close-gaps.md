# S7 — Close the gaps

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the SF ledger notes (this stage was spawned there, loose ends
> L1–L4) and the repo's `DECISIONS.md` area *Planning flow*, which covers the
> files below.

## Goal

Close the four small gaps the plan review found, so the new flow works from a
cloud session in any repo and the method and validator describe what was
built. Small, mechanical edits — no new behaviour beyond what the frozen
decisions already settle.

## Steps

- [ ] **Validator lists every template (L1).** Add `BRIEF.md` and `RUNNER.md`
  to `TEMPLATE_FILES` in `scripts/validate_plugin.py`, so a missing template
  fails validation.
- [ ] **The decisions spec reaches a cloud SF (L2).** In
  `commands/plan-stages.md` step 6, copy
  `references/decisions-format.md` into `.plan/` alongside the templates (same
  plain-copy rule, nothing else in the command), and say why in one clause:
  the final review stage reads `.plan/decisions-format.md` first, and a cloud
  session has no plugin to fall back on. Add the file to the `.plan/` file
  list in `skills/staged-rollout/references/templates/README.md` and in
  `docs/reference.md` › *Plan files*.
- [ ] **Unattended table row for the close triage (L3).** In
  `skills/staged-rollout/SKILL.md` › *Unattended mode*, add a row: decision
  point "The final review stage's kept-decisions list"; interactive "asked in
  one batch"; unattended "the stage applies its own proposals, and merging the
  plan→main PR approves them; an ambiguous decisions target is a **hard stop**
  for that step only".
- [ ] **The method names "decisions in force" (L4).** In `SKILL.md`, where the
  stage-session protocol is described, add one or two sentences: at the start
  of each stage the session is shown the decisions-document entries whose
  `Paths:` overlap the stage file's `## Artifacts`, and the brief's stamp is
  checked against `PLAN.md`. Point at the template's protocol rather than
  restating it.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes; with `BRIEF.md` temporarily
  renamed it fails naming that template (restore it after) — paste both
  outputs.
- `grep -n "decisions-format.md" commands/plan-stages.md` shows the copy in
  step 6.
- `grep -n "kept-decisions" skills/staged-rollout/SKILL.md` shows the new
  Unattended mode row, and `grep -n -i "decisions in force"
  skills/staged-rollout/SKILL.md` shows the method line.

## Artifacts

- `scripts/validate_plugin.py`
- `commands/plan-stages.md`
- `skills/staged-rollout/SKILL.md`
- `skills/staged-rollout/references/templates/README.md`
- `docs/reference.md`
