# S1 — Measure stage size

Issue: by-carlos/plan-staged-rollout#227

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. The `Issue:` line above is not a flag — it only
records which issue this stage came from, and `/stage-run` and `/plan-close`
print it. It is optional; a stage without it runs unchanged. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.
> Also read D-5 and D-15 in PLAN.md; this stage amends D-15.

## Goal

Measure past stage sessions on this machine (the transcripts exist only here,
and the figures need the user's eyes before they reach this public repo, hence
`gate: human`, D-5) and use the figures to pick what makes a stage too big
(D-15). S6 writes the resulting guidance into SKILL.md › *Decomposing the
work*.

## Steps

- [ ] Write a script in the session scratchpad (not committed) that combs local
  Claude Code session transcripts of past staged-rollout stage runs (sessions
  that ran `/stage-run` or followed `.plan/RUNNER.md`) and reports, per stage
  session: wall-clock duration, number of user messages after the first
  (interventions), compactions, and token totals if present. Scope: this
  repository's own sessions only by default; other projects' sessions only
  after the user's yes, and then pooled with no per-project labels. The script
  reads structured fields only and never prints message text, file paths,
  session IDs or project names. Its output is one fixed aggregate table with
  ordinal labels (stage session 1, 2, …).
- [ ] Check there are enough sessions to say anything, and state the count.
- [ ] Run the script. Report figures only, no private project detail (D-5).
- [ ] Amend D-15 in `.plan/PLAN.md` with the figures, the chosen measure
  (interventions, compactions, hours or story points) and threshold, and the
  recommendation of smaller stages or in-stage checkpoints. Regenerate
  `.plan/BRIEF.md` in the same commit.
- [ ] Paste the script's summary output into the ledger notes.
- [ ] Before the first push, show the user the full stage diff and wait for
  their OK (D-5): nothing from the transcripts is pushed unseen.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- The script's summary output is pasted into the ledger notes.
- D-15 in `.plan/PLAN.md` names the sample size and the figures, and the
  chosen measure and threshold.
- A grep of this stage's diff (the commits on the stage branch) for personal
  paths, `C--`-style project folder names, hostnames, email addresses and
  token-like strings returns nothing; paste the grep command and its empty
  output into the ledger notes.

## Artifacts

- `.plan/PLAN.md` (D-15 only)
- `.plan/BRIEF.md` (regenerated)

## Notes

- Depends on nothing; `gate: human` because the transcripts are on this machine
  only and the user checks the diff before it is pushed, so no driver runs it.
- The script stays in the session scratchpad and is not committed. Nothing
  private enters the repo: only figures.
- Tokens and story points stay in the measure: #227's problem statement and
  design call 6 name them.
- S6 consumes the amended D-15 when it writes the stage-size guidance.
