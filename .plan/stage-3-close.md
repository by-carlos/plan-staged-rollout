# S3 — Close-time triage

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read `decisions-format.md` under `skills/staged-rollout/references/`.

## Goal

The final review stage proposes and writes the lasting record; closeout carries
the list into the plan→main PR. This is what makes decisions survive `.plan/`
deletion.

## Steps

- [x] Rewrite `skills/staged-rollout/references/templates/stage-f-review.md`: keep its three-outcome checklist and add the decision triage per D-1 (attended batch ask vs unattended listing in the PR body), D-6 (existing ADR folder or decisions doc as target) and the spec's keep rule.
- [x] Add the README update item, the `CLAUDE.md` pointer line item, and the cold-reader check: a fresh subagent with only the repo and no `.plan/` answers "how do I test this, where is X, why Y"; every miss is a README or `DECISIONS.md` gap.
- [x] Edit `commands/plan-close.md`: the PR body template gains a kept-decisions section, filled from the final review stage's list.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- `stage-f-review.md` keeps its three-outcome checklist and gains the decision triage, README, pointer and cold-reader items — show the headings in the ledger notes.
- `plan-close.md`'s PR body template has a kept-decisions section.

## Artifacts

- `skills/staged-rollout/references/templates/stage-f-review.md`.
- `commands/plan-close.md`.
