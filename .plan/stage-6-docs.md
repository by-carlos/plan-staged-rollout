# S6 — Docs, lens checks and changelog

Issue: by-carlos/plan-staged-rollout#227

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the ledger notes of S1 and S5; D-12 and D-13 are the decisions
> this stage writes down. Do not bump the plugin version.

## Goal

Add two review checks, then bring the user documentation, examples and
changelog in line with every behaviour change in the plan, so nothing stale is
left for the final review to find. The checks: the Operator lens flags a
protective change (a guard or alert) that would wait on the plan branch
(D-12), and a pass threshold must say why that number and whether the check
can detect the difference (D-13). The changelog records what changed without
declaring a version, per the repository's `CLAUDE.md` › Releasing.

## Steps

- [ ] In `plan-review.md`, add to the Operator lens "Reads for" a protective
  change waiting on the plan branch, recommended as its own first plan or a
  `work-issue` ticket.
- [ ] In `plan-review.md`, add to the Simplicity lens "Reads for" a pass
  threshold without a basis.
- [ ] In the `stage-N.md` template, add one line to the acceptance section: a
  threshold says why that number and whether the check can detect the
  difference.
- [ ] Find the `docs/*.md` pages that describe gates, stage numbering, the
  final review or closing (by grep) and update them; update the README if it
  lists the stage flags.
- [ ] `SKILL.md` › *Decomposing the work*: write the stage-size guidance from
  D-15 only.
- [ ] Update (or note) example plans under `examples/` that use a suffixed ID
  or the old SF outcomes.
- [ ] Add the `CHANGELOG.md` entry under `## [Unreleased]`; no dated heading,
  no version bump, per `CLAUDE.md` › Releasing.
- [ ] Run the acceptance checks and paste the output into the ledger notes.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- The two lens rows and the template line read as described in the Steps
  (quote them in the ledger notes).
- `grep -rn "New stage in this plan\|S12b"` shows no stale guidance outside
  legacy-reading notes.
- The changelog entry is present under `## [Unreleased]`.

## Artifacts

- `skills/staged-rollout/references/plan-review.md` (Operator and Simplicity lens rows)
- `skills/staged-rollout/references/templates/stage-N.md` (the acceptance line)
- `docs/*.md` pages that describe gates, stage numbering, the final review or closing (found by grep)
- `README.md` (only if it lists the stage flags)
- `skills/staged-rollout/SKILL.md` (*Decomposing the work*, stage-size guidance from D-15 only)
- example plans under `examples/` that use a suffixed ID or the old SF outcomes
- `CHANGELOG.md` (under `## [Unreleased]` only)

## Notes

- Depends on S1 and S5: consumes S1's measured decision (amended D-15) and
  S5's final-review behaviour (and through it S2, S3 and S4).
- Shares `SKILL.md` with S0, S4 and S5; this stage touches only *Decomposing
  the work*, after S4 has landed.
