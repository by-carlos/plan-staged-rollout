# SF — Plan review

Issue: by-carlos/plan-staged-rollout#226

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md` — the *entire* ledger, every note, gotcha, shortcut, and
> known gap. This is the one stage exempt from the read-scope rule: read
> everything, not just what this stage depends on. Follow the protocol,
> including the finish protocol.

## Goal

Catalog every loose end the plan accumulated and close each one out. This
stage never implements — it only sorts findings into one of three outcomes
and records them.

## Steps

- [ ] Read every ledger row's notes end to end; list every loose end, gotcha,
  shortcut, and known gap surfaced across all stages.
- [ ] For each loose end, resolve it into exactly one outcome:
  - **New stage in this plan** — add a **PLAN.md stage index row** (with its
    `depends` / `mode` / `exec` / `model` / `effort` / `gate` flags — the index is the
    authoritative home, so `/stage-run`'s weight check and next-runnable logic
    can see the stage), a ledger row, and a stage file; it runs later as a
    normal stage in its own fresh session and branch.
  - **Spin-off candidate** — record it in the ledger and note it for the
    final PR body as follow-up; it does not block closeout.
  - **Accepted, won't fix** — write a one-line reason in the ledger so the
    gap is a decision, not a surprise.
- [ ] Confirm no loose end was dropped: every item from the first step maps
  to exactly one of the three outcomes above.
- [ ] Walk each of the eight "When this closes" items in issue #226
  (`gh issue view 226 --repo by-carlos/plan-staged-rollout --json body`) and
  record **met** or **not met** for each, with evidence (a file and heading, or
  a command and its output) in the ledger notes. A "not met" item is a loose
  end and goes through the three outcomes above.
- [ ] Apply D-10: dogfood the close-time decision triage using the repo's
  rewritten template (`skills/staged-rollout/references/templates/stage-f-review.md`,
  as changed by S3), not the older copy in `.plan/`. Propose drop /
  `DECISIONS.md` entry / ADR for every frozen decision, and write only the
  approved ones. This repo may gain its first `DECISIONS.md` and `CLAUDE.md`
  pointer line.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- Every loose end captured from the ledger is either a new stage (a PLAN.md
  stage index row **plus** a ledger row **plus** a stage file) or explicitly
  closed (spin-off note or accepted-won't-fix reason) — paste the resulting
  list into the ledger notes as evidence.
- Each of issue #226's eight "When this closes" items is recorded met / not
  met, with evidence, in the ledger notes.
- The D-10 close-time triage ran from the repo's rewritten template, and each
  frozen decision (D-1 … D-10) has a recorded outcome: drop, `DECISIONS.md`
  entry or ADR.
- `python3 scripts/validate_plugin.py` passes.

## Artifacts

Any new stage index rows, ledger rows, or stage files this review spawned, plus
what the D-10 close triage writes if approved: a possible first `DECISIONS.md`,
ADRs, a README update and a `CLAUDE.md` pointer line. No product code — this
stage never builds anything itself.
