# S6 — Example plan

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read `examples/README.md` and one existing example plan for conventions,
> plus the S0–S3 ledger notes.

## Goal

One example plan under `examples/` shows every new artifact, so a reader sees
the finished shape without running a plan.

## Steps

- [ ] Create a new folder under `examples/` for the example plan, following the existing examples' layout.
- [ ] Show the Requirements section and the triage groups on its decisions in the example `PLAN.md`.
- [ ] Add a filled `BRIEF.md` with its stamp line and Mermaid day-to-day flow.
- [ ] Add a plan-review digest with the three outcomes applied to findings.
- [ ] Add close-time `DECISIONS.md` outcomes: one dropped decision, one entry, one ADR.
- [ ] List the new example in `examples/README.md`.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `python3 scripts/validate_plugin.py` passes.
- Each of the five items appears (requirements section, triage groups, filled brief with stamp and Mermaid flow, plan-review digest with outcomes, close-time outcomes) — list file and heading per item in the ledger notes.

## Artifacts

- A new folder under `examples/`.
- `examples/README.md`.
