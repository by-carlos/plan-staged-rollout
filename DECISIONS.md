<!-- decisions-format: 1 -->
# Decisions

Decisions in force. Read the area that covers a path before changing it; add
or edit an entry in the same pull request when a change settles something
future work must respect.

## Planning flow

Paths: `commands/plan-stages.md`, `commands/plan-close.md`, `skills/staged-rollout/SKILL.md`, `skills/staged-rollout/references/plan-review.md`, `skills/staged-rollout/references/templates/`

- **The plan review runs inside `/plan-stages`, on the uncommitted scaffold,
  never as a standing stage before S1; the close-time decision triage runs in
  the final review stage (SF), never in `/plan-close`.** — a standing review
  stage costs every plan one more session and one more human gate, and
  closeout runs unattended. Revisit: if a scaffold grows too big to review in
  the bootstrap session. Source: #226
- **`.plan/BRIEF.md` is the brief: generated from `PLAN.md`, stamped with
  `PLAN.md`'s hash, never hand-edited; an artifact only renders it.** — the
  file works on every surface (cloud, terminal, phone), so there is one
  output, not two by environment. Revisit: never. Source: #226
- **The Simplicity lens always runs; Architect, Security and Operator run only
  when their triggers fire — never all four by default.** — all four on every
  plan doubles the review's cost. Revisit: if effort-log data or a missed
  finding shows a trigger is too narrow. Source: #226
- **Bootstrap overhead is measured from the effort log, not gated: the target
  is under ~15% of a plan's sessions, with at most four lenses and a ~40-line
  digest.** — no real plan ran inside the plan that built this, so a gate
  would have been a guess. Revisit: once a real plan's `plan-stages` row can
  be read off the log. Source: #226
- **Plan versus ticket uses the existing line (about four or more sessions);
  there is no other size metric, and work handled by `work-issue` gets no
  brief and no plan review.** — stage count is known only after decomposing,
  and not every plan starts from a sized issue. Revisit: never. Source: #226
- **`/plan-stages` ends by offering one session card per wave-0 stage, through
  `stage-run`'s desktop-app chip step; the printed command stays the handoff
  on every other surface.** — the desktop app can start top-level sessions,
  so forbidding the offer was wrong. Revisit: if the chip tools change.
  Source: #226

## Decisions format

Paths: `skills/staged-rollout/references/decisions-format.md`

- **`decisions-format.md` stays self-contained, with no plugin-specific
  content; any change bumps its version line and lands identically in
  by-carlos/daikenja.** — Daikenja carries an identical copy, and two copies
  with one version must match. Revisit: never. Source: #226,
  by-carlos/daikenja#292
