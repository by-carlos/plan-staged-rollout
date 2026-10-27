<!-- decisions-format: 1 -->
# Decisions

Decisions in force. Read the area that covers a path before changing it; add
or edit an entry in the same pull request when a change settles something
future work must respect.

## Planning flow

Paths: `commands/plan-stages.md`, `commands/plan-close.md`, `skills/staged-rollout/SKILL.md`, `skills/staged-rollout/references/plan-review.md`, `skills/staged-rollout/references/programme-format.md`, `skills/staged-rollout/references/templates/`, `skills/staged-rollout/scripts/renumber_stages.py`

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
- **`/plan-stages` proposes a programme when the requirements hold two or more
  outcomes that can each merge into `main` alone — a count of outcomes, never
  of stages.** — stages are known only after decomposing, and a stage count
  would be the second size metric the line above rules out. Revisit: never.
  Source: #227
- **A milestone reaches `main` only by closing its own plan: there is no
  milestone merge inside a plan, and no guard against GitHub's
  `delete_branch_on_merge`.** — a plan branch is only ever the head of its
  final PR, so deleting it on that merge removes nothing still needed.
  Revisit: if a plan ever merges into `main` more than once. Source: #227
- **The final review stage (SF) never adds a stage, except a `Fix:` stage that
  repairs a named requirement, failing Done check or regression — made with
  the user present, at most 3 per plan (a fourth is a hard stop), after which
  SF re-runs from the top; SF writes its documentation only on a clean
  pass.** — found work leaves the plan as an issue or a later plan, as in
  Scrum, PRINCE2 and AWS AI-DLC (whose loop-back is capped at 3); a strict
  no-exception rule would let a plan close on a failing Done check.
  Revisit: if a real plan hits the cap. Source: #227
- **A programme's `PROGRAMME.md` on `main` lists its plans as ordered pointers
  with no state column; each `/plan-close` removes its own line, and the last
  removes the file.** — a state column would copy what each plan's ledger and
  PR already hold. Revisit: never. Source: #227
- **A wait measured in days is never a stage: it becomes a dated follow-up
  issue stating the date, the check, the pass condition and the action on
  failure, and nothing is scheduled.** — a wait row would put a non-stage in
  the stage table, and scheduling is outside the plugin's tools.
  Revisit: if the plugin gains a reminder tool. Source: #227
- **Stage IDs are plain numbers plus `SF`, in running order; a suffixed ID
  (`S12b`) is never created but is still read.** — a started stage keeps its
  ID, so plans in flight keep running. Revisit: once no plan in flight carries
  a suffixed ID. Source: #227
- **`renumber_stages.py` renumbers only unstarted stages (status `todo`, no
  stage branch, no `BLOCKED.md` section) and uses the standard library
  only.** — a started stage's number is baked into its branch, worktree and
  PR. Revisit: never. Source: #227
- **A stage is too big when a run of it needs more than 4 interventions or
  more than 1 hour of active time; split it rather than add in-stage
  checkpoints.** — over 46 past stage sessions, time tracked interventions and
  context never did (no compaction up to 376K tokens). Revisit: when a
  designed sample can separate stage types, or count only unprompted
  interventions. Source: #227
- **A stage's `Issue:` line is closed only by the final PR's merge: `/plan-close`
  writes `Closes <ref>` for each linked issue (`Refs` for one `SF` records as
  not fully delivered, or while `PROGRAMME.md` lists another plan), and no
  command posts to an issue or changes its status.** — a person merging the PR is the approval, as it is for kept
  decisions, and a reference without the keyword left #227 open after its
  plan merged. Revisit: if a plan's final PR ever targets a branch other than
  the default. Source: #250

## Running stages

Paths: `commands/stage-run.md`, `commands/plan-run.md`, `hooks/session-start`, `skills/staged-rollout/references/remote-driver.md`, `skills/staged-rollout/references/templates/RUNNER.md`

- **A runner fires a stage only when its `gate` is `auto` or absent; `human`,
  `local`, `live` and any unknown value are refused and named.** — an
  allow-list fails safe when a new gate value appears. Revisit: never.
  Source: #227
- **Never two `live` stages at once: `/stage-run` refuses at start when
  another `live` stage has a branch or worktree open; the session-start hook
  only notes it.** — `live` changes a running system, and the refusal reuses
  preflight's live-sibling signature rather than a new lock. Revisit: if a
  plan needs two `live` stages on unrelated systems. Source: #227

## Decisions format

Paths: `skills/staged-rollout/references/decisions-format.md`

- **`decisions-format.md` stays self-contained, with no plugin-specific
  content; any change bumps its version line and lands identically in
  by-carlos/daikenja.** — Daikenja carries an identical copy, and two copies
  with one version must match. Revisit: never. Source: #226,
  by-carlos/daikenja#292
