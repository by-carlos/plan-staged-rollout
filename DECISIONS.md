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
  writes `Closes <ref>` for each linked GitHub issue (`Refs` for one `SF`
  records as not fully delivered, or while `PROGRAMME.md` lists another
  plan), and always `Refs <url>` for a Jira ticket, which a pull request
  cannot close.** — a person merging the PR is the approval, as it is for kept
  decisions, and a reference without the keyword left #227 open after its
  plan merged. Revisit: if a plan's final PR ever targets a branch other than
  the default. Source: #250
- **Drift is judged by kind, not amount: a fresh-context scope referee checks
  each stage added after the scaffold against the plan's Outcome and Out of
  scope, and only its "different plan" verdict stops the session; nothing but
  adding a stage triggers it, and there is no threshold.** — a fixed
  threshold is arbitrary and noisy, and the session that drifted is the worst
  judge of its own drift. Revisit: if real plans show the referee too quiet or
  too noisy. Source: #229
- **Inside a running stage, drift is prevented, not caught: a stage's
  Acceptance is its stop line, so more of the same work after it passes is a
  new stage through the scope referee, and each stage records an
  `Artifacts check:` line (`match`, `undeclared` or `outside`) that only the
  final review judges.** — a check at a stage's end cannot save that stage's
  work, a file mismatch is a weak drift signal (zero real drift across this
  repo's first six stage PRs, and both raw mismatches were parsing noise), and
  `## Artifacts` stays free prose, read for backticked paths only, so no
  existing plan changes. Revisit: if recorded `outside` lines turn out to be
  real drift, which would justify pausing the stage PR's merge on them.
  Source: #259
- **An idea too vague to state its Done checks, or whose checks name nothing
  a script could assert or a person could see (or leave the Outcome
  uncovered), gets a discovery plan as the recommended answer; its Out of
  scope reads `Building <subject> — that is the next plan.`; and a build plan
  from such requirements is never refused but needs the user's reason,
  recorded as a frozen decision with the drift risk.** — a warning alone is
  waved through and a refusal only pushes people past every guardrail, while
  the referee needs a written boundary, not a resemblance. "Thin" is kept
  narrow (unranked constraints and a short Out of scope do not count) so
  clear plans are never nagged, and the gate adds no question round. An
  Outcome with no edge ("exhaustive", "everything", "etc." with no list of
  what it covers) is thin too, and checks the session writes cannot clear
  it — only the user's list can — because such checks pass while the scope
  grows (an exhaustive-analysis ask otherwise scaffolds open-ended stages
  unchallenged). Applies to plans scaffolded after it; earlier plans are not migrated. Revisit: if
  real plans show the thin check nagging clear requirements, or reasons
  given that never held. Source: #261
- **Lessons at close are three to six blunt, evidence-backed lines in two
  groups, kept only in the final PR body and read back by the next
  `/plan-stages` in the same repository; there is no retro file, and work done
  as a single ticket gets none.** — a retro kept as a record changes nothing;
  the next plan's playback is where a lesson can still act. Revisit: if
  lessons need to reach plans in other repositories. Source: #229
- **A plan-review finding needs a location, a concrete consequence and a
  change, or the digest drops it; a Security finding also names a plausible
  actor and path. A lens may add a one-line unsound verdict, which always
  reaches the user.** — a location and an edit alone let box-ticking findings
  through, and the review should help the plan move, stay quiet when nothing
  matters, and flag bluntly only what is broken. Revisit: if real plans show
  a genuine risk dropped for lack of a stated actor. Source: #276

## Running stages

Paths: `commands/stage-run.md`, `commands/plan-run-cloud.md`, `commands/plan-run-local.md`, `skills/staged-rollout/scripts/plan_run_local.py`, `hooks/session-start`, `skills/staged-rollout/references/remote-driver.md`, `skills/staged-rollout/references/templates/RUNNER.md`, `skills/staged-rollout/references/estimates.md`, `skills/staged-rollout/scripts/estimates.py`, `skills/staged-rollout/scripts/effortlog.py`

- **A runner fires a stage only when its `gate` is `auto` or absent, and the
  local runner (`/plan-run-local`) also `local`; `human`, `live` and any
  unknown value are refused and named by every runner.** — an allow-list
  fails safe when a new gate value appears, and `local` means "never by a
  driver that could be running anywhere but the local machine", which the
  local runner cannot be. Revisit: never. Source: #227, #266
- **The local runner is a standard-library Python driver started in the
  background by an interactive orchestrator session; the driver holds the
  loop, and the session reads only its one `STATUS:` line.** — a headless
  orchestrator lost its background command when its `-p` run ended (CLI
  2.1.268), only a session can reach the user and pass an ask-rule merge,
  and a script keeps the session's context flat. The cloud runner stays
  model-driven (`remote-driver.md`). Revisit: if Claude Code gives headless
  runs long-lived background commands. Source: #266
- **The local runner checks each stage session's opening line for the
  permission mode, model and effort it asked for, and stops a mismatch before
  any work; it never works around a managed setting.** — auto mode turned off
  by an organisation starts `--permission-mode auto` sessions in Manual
  without an error, and a headless Manual session denies everything and keeps
  spending. Revisit: if the CLI refuses an unavailable mode instead.
  Source: #266
- **The local runner reads a stage whose plan-branch row never moved, but
  whose stage branch it pushed or updated during the run, as stopped, not
  dead.** — a stage records `doing` on its own branch, so a merge refused
  under `-p` leaves the plan branch reading `todo`; calling that dead hid the
  merge offer (measured in the #266 end-to-end run). A stage branch left from
  an earlier run does not count. Revisit: if stages start pushing `doing` to
  the plan branch. Source: #266
- **The cloud runner reads the same signature the same way, and re-fires the
  stage after the person's merge.** — it records the stage's remote branches
  when firing; after the grace period an unmoved row with a branch created or
  moved since then is a stop with a merge pending, not a dead run, and the
  orchestrator offers the merge (`Merge?`, the person's yes only). Re-firing
  lets the fresh session's preflight record `done`, so the orchestrator still
  never writes the ledger and the run stays hands-off, at the cost of one
  short cloud session. Rejected: pushing `doing` to the plan branch before
  the PR (changes the protocol every plan carries), and rewording the dead
  report only (the person still diagnoses a merge as a crash). Revisit: if a
  cloud run shows the re-fired session does not record `done`, or if stages
  start pushing `doing` to the plan branch. Source: #268
- **The local runner's settings are environment variables
  (`CLAUDE_STAGE_LAUNCHER`, `CLAUDE_STAGE_PERMISSION_MODE`,
  `CLAUDE_STAGE_IDLE_MINUTES`, `CLAUDE_STAGE_MAX_BUDGET_USD`); the launcher is
  one executable with no arguments, and the plugin never reads a secret.** —
  no shell-quoting rules that differ between PowerShell and POSIX, and a login
  wrapper stays the user's. No dollar cap by default, in line with the
  tokens-only usage rule. Revisit: if the plugin gains a settings file.
  Source: #266
- **The local runner keeps its status file and logs in the clone's git
  directory (`plan-run-local/<slug>/`), never in `.plan/`, and stops at plan
  completion instead of running closeout.** — nothing to commit or ignore,
  and closeout opens the PR into `main`, a moment the user should be present
  for. Revisit: if users ask for a hands-off closeout. Source: #266
- **Never two `live` stages at once: `/stage-run` refuses at start when
  another `live` stage has a branch or worktree open; the session-start hook
  only notes it.** — `live` changes a running system, and the refusal reuses
  preflight's live-sibling signature rather than a new lock. Revisit: if a
  plan needs two `live` stages on unrelated systems. Source: #227
- **An unattended session never adds a stage, whichever command or runner
  fired it: the work is noted for the final review instead.** — the scope referee's
  "different plan" verdict needs a person to choose. Revisit: if the referee
  gains a declared default. Source: #229
- **Stage actuals come from the session's own transcript, and usage is
  reported in tokens only — no dollar cost, no share of a usage limit.** —
  the transcript is the one source in the CLI, the desktop app and cloud
  sessions alike; a price table goes stale and means nothing on a
  subscription, and a usage limit is shared with other sessions. Revisit: if
  Claude Code exposes a per-session cost or limit share everywhere.
  Source: #228
- **Estimates are ranges in hours, judged against written anchors and scaled
  by the median actual-to-estimate ratio of past `stage-run` rows (three or
  more) in the effort log; the plan total is computed by
  `estimates.py`, never by hand.** — no size column to fill and drift, and
  `effort` measures reasoning depth, not work. Revisit: once the log is large
  enough to replace the anchors by stage kind. Source: #228
- **While a stage runs, `/stage-run` moves its linked ticket only to the
  template's `[work].status` names (`on_start` at a fresh start, `on_pr` when
  the stage PR opens), with one fixed-text comment each, never to a done
  status; the declared status authorizes it unattended, and a failed write
  never stops the stage.** — the board tracks the plan without hand moves,
  and closing stays the final merge's job; `work_core.py stage-status` holds
  the rules so no run drifts. Rejected: one ticket per stage (deferred), and
  asking before each comment (unattended could never post). Revisit: if
  per-stage ticket creation lands. Source: #292

## Tickets

Paths: `skills/create-issue/SKILL.md`, `tickets/references/gap-rubric.md`, `tickets/scripts/ticket_core.py`

- **The gap review trims as well as asks, through nits only, and never by a
  word count.** — every earlier check could only add text, which inflated
  small tickets; a trimming nit costs no question and is listed for the user
  to restore at the approval gate, while a size limit would force cuts or
  padding the work does not justify. Revisit: if trimmed tickets start
  losing information that later comes back as a question. Source: sample of
  20 AI-written tickets, 2026-11-11
- **The AI prompt is the one section that repeats on purpose: it restates
  every guardrail and stops when it disagrees with the description.** —
  `work-issue` follows no instruction outside the prompt, so a guardrail
  written only in the description never reaches the agent. Revisit: if
  `work-issue` ever reads the description as instructions. Source: same

## Decisions format

Paths: `skills/staged-rollout/references/decisions-format.md`

- **`decisions-format.md` stays self-contained, with no plugin-specific
  content; any change bumps its version line and lands identically in
  by-carlos/daikenja.** — Daikenja carries an identical copy, and two copies
  with one version must match. Revisit: never. Source: #226,
  by-carlos/daikenja#292
