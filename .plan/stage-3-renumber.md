# S3 — Renumbering script

Issue: by-carlos/plan-staged-rollout#227

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read S0's ledger notes and the ID rule it wrote in the PLAN.md
> template; D-9 and D-10 are the decisions this stage implements. Match the
> style of the existing `effortlog.py` and `test_preflight_ahead.py`.

## Goal

Build the script that renumbers the unstarted stages after an edit to the stage
index, so numbers follow running order without touching a started stage
(D-10). S5 uses it for the fix-insertion path.

## Steps

- [x] Write `renumber_stages.py` (standard library only) with one operation, in
  place: renumber the unstarted stages that follow the edited stage index; git
  on the stage branch is the undo, so there is no insert mode and no dry-run
  flag. A stage counts as **started** when its ledger status is not `todo`,
  when a `plan-<slug>-s<N>` branch exists, or when `.plan/BLOCKED.md` has a
  section for it; a started stage keeps its number. The script rewrites the
  stage index, the stage file names, the ledger rows, every `depends` cell,
  the `.plan/BLOCKED.md` sections, and the `S<N>` references in stage-file
  prose. The caller regenerates `.plan/BRIEF.md` in the same commit. It
  refuses a suffixed new ID.
- [x] Make it safe on untrusted index cells: validate every `File` cell and
  every stage ID against the grammar, keep every path inside `.plan/`, refuse
  symlinks, and exit before any write on a refusal.
- [x] Write `test_renumber_stages.py` with a fixture plan, in the same test
  framework as `test_preflight_ahead.py`; it covers each refusal (suffixed ID,
  a `File` cell outside the grammar, a path escaping `.plan/`, a symlink) and
  the started-stage cases (non-`todo` status, an existing stage branch, a
  `BLOCKED.md` section).
- [x] In the PLAN.md template, point the "adding a new stage" sentence at the
  script.
- [x] Run the test and a fixture renumbering; paste the output into the ledger
  notes.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- The test passes (`python3 -m unittest` or pytest, whichever the existing
  `test_preflight_ahead.py` uses).
- A fixture run after an edit to the stage index shows only unstarted stages
  renumbered (index, file names, ledger rows, `depends`, `BLOCKED.md`
  sections, prose references) and SF still last.

## Artifacts

- `skills/staged-rollout/scripts/renumber_stages.py`
- `skills/staged-rollout/tests/test_renumber_stages.py`
- `skills/staged-rollout/references/templates/PLAN.md`

## Notes

- Depends on S0: consumes its ID rule (plain numbers plus `SF`, suffixed IDs
  never created) and its numbering rule (running order; side-by-side stages get
  consecutive numbers).
- S5 consumes this script for adding a D-4 fix before SF.
- The PLAN.md template is also written by S0 and S5; S0 precedes this stage
  and S5 follows it, so the edits do not overlap in time.
