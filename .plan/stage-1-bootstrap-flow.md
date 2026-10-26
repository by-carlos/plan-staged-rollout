# S1 — Bootstrap flow

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read the formats S0 wrote: `decisions-format.md`, `templates/BRIEF.md`
> and `plan-review.md` under `skills/staged-rollout/references/`.

## Goal

`/plan-stages` runs requirements, playback, triage, one batch ask, decompose,
scaffold, brief, lens review, then the scaffold commit. This is the entry point
the maintainer uses; the other stages hang off what it produces.

## Steps

- [ ] Rewrite `commands/plan-stages.md` step order per D-1, D-2, D-4, D-6 and D-7: requirements step and playback, decision triage with one batch ask, decomposition, scaffold, brief generation, lens review, then the commit.
- [ ] Add the effortlog row per D-5: `/plan-stages` logs a row, including review subagents' tokens.
- [ ] Add `plan-stages` to the `--source` choices in `skills/staged-rollout/scripts/effortlog.py`.
- [ ] Rewrite the end announcement per D-11: offer a card per wave-0 stage, reusing `commands/stage-run.md`'s desktop-app chip step rather than restating it.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- `python skills/staged-rollout/scripts/effortlog.py log --help` lists `plan-stages`.
- `grep -n "top-level sessions" commands/plan-stages.md` finds nothing, and the end announcement points at `/stage-run`'s chip step (D-11).
- The command file's step order shows requirements and triage before any frozen decision, and the review before the scaffold commit — quote the step headings into the ledger notes.

## Artifacts

- `commands/plan-stages.md`.
- `skills/staged-rollout/scripts/effortlog.py` (`--source` gains `plan-stages`).
