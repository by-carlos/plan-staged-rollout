# S5 — User docs and changelog

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the S1–S4 ledger notes and the files they changed, so the docs
> describe behaviour as built.

## Goal

Users can learn the new planning flow from the docs. This stage is the only one
that writes `CHANGELOG.md` (D-9).

## Steps

- [x] Update `docs/staged-rollout.md` with the requirements step, triage, brief, plan review and close-time triage, as built in S1–S4.
- [x] Update `docs/reference.md` for the new commands, files and formats.
- [x] Add one feature entry under `## [Unreleased]` in `CHANGELOG.md`, referencing #226 (D-9). No version heading, no `plugin.json` bump.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes (it checks docs links).
- `CHANGELOG.md` has exactly one new `## [Unreleased]` entry referencing #226 — paste the entry into the ledger notes.

## Artifacts

- `docs/staged-rollout.md`.
- `docs/reference.md`.
- `CHANGELOG.md`.
