# How a staged rollout works

## 1. Bootstrap — `/plan-stages <project idea>`

Runs once. If the design isn't settled, it starts with a design pass
(using `superpowers:brainstorming` when installed, or a built-in lightweight
question flow otherwise) — the outcome lands directly as **frozen decisions**,
not as a separate spec that would become a second source of truth. Then it:

- gates on session weight first: bootstrap is the highest-leverage session of
  a plan, so it requires at least an Opus-class model (verified from the
  session) and recommends medium-or-higher effort (read from `CLAUDE_EFFORT`),
  offering to abort so you can relaunch appropriately;
- decomposes the work into the smallest sensible stages with explicit
  `depends`, putting the keystone (the piece everything needs) as S0;
- appends a standing **final review stage** (see below);
- prints the **wave structure and critical path** derived from `depends`, so
  a fan-out is visible before you start — and so is a plan accidentally
  decomposed into a chain;
- records the fixed git and worktree model (branch-per-stage, worktree-per-stage
  — below); it is not a choice you are asked to make;
- scaffolds `.plan/` and commits it. **No stage is executed during
  bootstrap.** It finishes by saying so explicitly and telling you exactly
  what to run next: the first stage's command and its recommended
  model/effort.

```
<repo>/.plan/
  README.md          # entry point + how to run a stage
  PLAN.md            # architecture, frozen decisions, stage index,
                     #   operating protocol  ← single source of truth
  LEDGER.md          # status table + per-stage as-built notes
  stage-N-<slug>.md  # one thin, self-contained stage each
```

The operating protocol lives *inside the scaffolded `PLAN.md`*, so a `.plan/`
folder is fully portable: anyone can run a stage with the one-line prompt
"Follow the instructions in `.plan/stage-N-<slug>.md`" even without this
plugin installed. The commands are ergonomics, not a dependency.

Want to see what a filled-in scaffold looks like before running bootstrap on
a real project? [`examples/`](../examples/) holds a complete `.plan/` for a toy
project captured mid-rollout — a `done` stage with real acceptance evidence
pasted in the ledger, a `doing` stage with ticked checkboxes and a handoff
note — plus a tour of the discipline it demonstrates.

## 2. Execute — `/stage-run <N>` (repeat, one fresh session each)

The session follows the operating protocol in `PLAN.md`:

1. **Flag check.** Each stage recommends a model and effort level. The agent
   can't switch its own model, so these are honest *launch hints*: the model
   is verified from the session itself, the effort from `CLAUDE_EFFORT`, and on
   a mismatch it stops before any work and names the model and effort to
   relaunch with — there is no continue option. Attended, you can also switch
   them in place: change the model and effort in the session's model menu,
   then type **go** (or just **.**) and the stage re-checks and starts.
2. **Read only what's needed.** Frozen decisions + the stage file + the ledger
   table + notes of the stages it `depends` on. Never scan the repo.
3. **Dependency gate.** If a prerequisite isn't `done` or `skipped` in the
   ledger (and merged into the plan branch), stop.
4. **Honor `mode`.** `direct` = one-line plan, implement. `brainstorm` = a
   design pass scoped to this stage first, treating frozen decisions as settled.
5. **Honor `exec`.** `inline` = implement here. `subagent(<model>)` = act as
   orchestrator and dispatch implementation to a subagent so the churn stays
   out of this context.
6. **Scope discipline.** Do only this stage. Work spotted for another stage is
   noted in the ledger and left untouched — it may become a new stage.
7. **Finish protocol.** Run the acceptance check and record the *real output*;
   update the ledger row and notes; amend frozen decisions in `PLAN.md` (and
   nowhere else) if one changed; open the stage PR; announce the stage is
   finished and name **every** stage that is runnable now — each with its exact
   command and recommended model/effort, and whether they can overlap; stop.

**Subtasks and interruption.** Stage steps are checkboxes. If a session must
stop mid-stage (blocked, context getting long, you interrupt), it marks the
stage `doing`, ticks the completed boxes, and writes a handoff note.
Re-running `/plan-staged-rollout:stage-run <N>` (or asking to "run stage \<N>
of the plan" again) resumes from the unticked boxes.

**Statuses:** `todo → doing → done`, plus `blocked` (waiting on a human or an
external gate — the stage becomes a runbook with exact steps for you) and
`skipped` (decided against, one-line reason recorded). Partial completion is a
normal, resumable state, not a failure.

**Where a `blocked` record lands** depends on whether the stage's branch exists
yet, and the plan's own `PLAN.md` states the rule (*Operating protocol →
Recording a block*). A block that fires before the branch exists — the weight
check, a `gate: human`/`gate: local` backstop, a refused redo — is committed straight onto
the plan branch, so it is readable the moment it happens. A block that fires
mid-stage lands on the stage branch, where its runbook rides the stage PR, and
is announced on the plan branch through a `### S<N>` section in
`.plan/BLOCKED.md`. That second write is what makes a mid-stage block visible
without waiting for a merge.

## Starting the next stage from a chip (desktop app)

In the **Claude desktop app**, a finished stage also offers each next
runnable stage as a **suggestion chip** — click it instead of pasting the
command into a new session. Click the chip (top right of the window) and
choose **Start locally**:

| Launch mode | Use it? |
|---|---|
| **Start locally** | **Yes.** Runs in your clone, which the stage leaves on the plan branch while it works in its own worktree. |
| Start with worktree | Works, but the app's worktree is based on the default branch, so the stage ignores it and makes its own; the app's one is left behind unused. |
| Send to cloud | Works for a plan with `.plan/RUNNER.md`, but **may use additional credits**, and refuses a `gate: local` stage. For cloud runs, use [`/plan-run`](ON-THE-RUN.md#under-the-hood). |
| Fix in this session | **No.** It lands in the finished stage's session instead of a fresh one; the stage refuses to start there. |

- **The chip usually starts on the finishing session's model and effort**, not
  the stage's: a `spawn_task` chip has no way to set them, and a `start_session`
  card can only set them *at or below* the finishing session's. When the next
  stage asks for the same weight (or lighter, via `start_session`) it runs
  straight through; when not, it stops before any work and tells you what to
  switch to — switch in the model menu and type **go**.
- **Two chip tools exist, and a session may have only one.** Some desktop
  sessions offer `spawn_task`, others `start_session`; the stage-run step uses
  whichever is present. A `start_session` card is started by a click, or by
  telling Claude "start it".
- **No chip on a phone.** Following the session over Remote Control, or
  working in a terminal, shows no chip — paste the printed command into a
  fresh session instead. The printed command is always there; the chip is an
  addition, never a replacement.

## Session-start nudge

The real friction of a multi-day rollout isn't typing a long command — it's
that a fresh session doesn't know a rollout exists. A `SessionStart` hook
closes that gap: when the repo has a `.plan/` directory, every new session
starts already knowing every runnable stage — any `doing` stage to resume, plus
every `todo` whose `depends` are all `done` or `skipped` — with each stage's recommended
model/effort from the stage index and its exact `/stage-run` command. When more
than one stage is runnable it says so, so a fan-out is visible from the first
line of the session.

Deliberately narrow by design:

- **Zero cost elsewhere.** No `.plan/` at the repo root → the hook emits
  nothing. It only ever speaks in a repo with an active rollout.
- **It offers, never runs.** Execution still belongs to the operating
  protocol in `PLAN.md` — weight check, dependency gate, your go-ahead.
- **Fail silent.** Malformed ledger, missing bash, parse ambiguity → no
  output, exit 0. A session-start hook must never degrade a session.
- **Cross-platform.** The `.cmd` file is a cmd/bash polyglot wrapper, so the
  hook runs on Linux, macOS, and Windows (via Git Bash). Its one real
  dependency is `bash`; a Windows box without it simply gets no nudge — the
  rest of the plugin is unaffected, since the commands are model-driven, not
  shell scripts.

## Parallel stages — reported, not launched

`depends` is a real dependency graph, so a plan often has several stages
runnable at the same time. Every surface that answers "what's next" reports the
whole **runnable set** — every `todo` stage whose dependencies are satisfied —
never just the first:

```
3 stages are runnable right now — none depends on another, so they can be
run concurrently, one per fresh session:

- S1 — Parser       /stage-run 1   (model sonnet, effort low)
- S2 — Renderer     /stage-run 2   (model sonnet, effort med)
- S3 — CLI flags    /stage-run 3   (model haiku,  effort low)
```

Bootstrap prints the wave structure and critical path for the same reason: the
wave count is the fewest rounds the plan can take, and the critical path is the
floor on elapsed time that no amount of parallelism removes.

Two deliberate limits:

- **Waves are derived, never stored.** There is no `wave` or `parallel-group`
  column in the stage index. Waves are a view of `depends`, and a stored copy
  of a single source of truth is exactly what this method exists to prevent.
- **Launching is yours.** Running a wave in parallel means one session per
  stage — one [chip](#starting-the-next-stage-from-a-chip-desktop-app) click
  each in the desktop app, or one terminal each elsewhere. The plugin tells you
  what *can* overlap; whether to is your call. The
  [remote orchestrator](ON-THE-RUN.md#under-the-hood) removes the
  keyboard from *sequential* runs, not from this — it takes a multi-stage
  runnable set one stage at a time.

What makes that physically safe is worktree-per-stage: each session works in
its own directory on its own branch, so nothing contends for a checkout and no
session can see another's uncommitted work. Four further rules keep the
branches from colliding when they meet at the plan branch:

- **The plan branch is the serialization point.** Stage PRs merge one at a
  time, first come first served. Whoever merges second re-syncs — merge the
  plan branch *into* the stage branch, resolve there, and **re-run the
  acceptance check**, because "mergeable" means no textual conflict, not that
  the stage still passes after the sibling's change. Squash merge makes that
  free, which is why stage branches are never rebased or force-pushed.
- **A sibling's stage branch is not drift.** Preflight used to read any `todo`
  row with a committed stage branch as a crashed session and halt — which
  would stop every parallel session. It now classifies by whose stage the
  mismatch is: drift on *your* stage still stops you; another stage's
  in-flight branch is reported and stepped over.
- **Shared write territory is a `depends` edge.** Two stages that write the
  same files are not independent, whatever the feature graph says. There is no
  separate territory field — a second record of one constraint is a second
  thing to drift — so bootstrap checks for the overlap and adds the edge.
- **The `done` ledger write can race.** Both sessions commit it directly on
  the plan branch: edit after the fast-forward, replay with a rebase if the
  push is rejected, keep both rows on conflict, and never force-push the plan
  branch.

**Subagent fan-out is not a substitute.** Running a whole wave from one
orchestrator via `exec: subagent(<model>)` avoids git concurrency, but it
collapses N stages into one branch, one PR, one ledger row and one acceptance
check — and the orchestrator accumulates every subagent's return, so per-session
cost stops being flat, which is the mechanism this whole method rests on. Use
it *within* a stage for churn; if a wave really is one unit of work, merge
those stages at decomposition time instead.

## 3. Git & worktree model (fixed)

```
main
 └── plan-<slug>                    ← plan branch; .plan/ lives here
      ├── plan-<slug>-s0  → PR → plan-<slug>
      ├── plan-<slug>-s1  → PR → plan-<slug>
      └── ...
plan-<slug> → final PR → main       ← at /plan-close
```

On disk, that means your clone and one sibling directory per running stage:

```
~/src/
  myrepo/        ← your clone, always on plan-<slug>, holds .plan/
  myrepo-s1/     ← worktree, branch plan-<slug>-s1
  myrepo-s3/     ← worktree, branch plan-<slug>-s3   (running concurrently)
```

- **Every stage gets its own branch and PR into the plan branch** — no
  exceptions. Uniformity is the point: it keeps each unit reviewable in
  isolation, and it contains the classic failure where "one small commit"
  quietly becomes twenty commits of fixes bleeding into shared history.
- Branch names are flat (`plan-<slug>-s3`, not `plan/<slug>/s3`) because git
  refs can't nest a branch under an existing branch name.
- Feature-branch plumbing is autonomous: the agent **creates and pushes** stage
  and plan branches without asking, and **opens the stage PR** into the plan
  branch as a compulsory part of finishing a stage. Merges are **offered** and
  happen only on your OK — it never merges on its own, and never pushes to
  `main`. The one carve-out is a plan that sets `merge: auto` (see *Per-stage
  knobs*): that is your OK given in advance for **stage PRs only**, so the
  session squash-merges its own stage PR once checks are green; the plan→main
  PR stays yours in every mode. A stage cannot be marked `done` until its PR
  is merged.
- Merge type is fixed by position: stage PRs into the plan branch are
  **squash-merged** (one commit per stage, merged branch deleted); the final PR
  from the plan branch into `main` is a **normal (non-squash) merge**, so each
  stage lands on `main` as its own distinct commit.
- **Repo settings prerequisite:** the GitHub repo must allow both squash
  merging and merge commits. Recommended defaults: squash message = "Pull
  request title and commit details"; merge-commit message = "Pull request
  title and description" (so the distilled final-PR body lands in the merge
  commit on `main`).
- **Nothing enforces the merge type at the final merge — set the repo's
  default merge button to "Create a merge commit."** The plan-to-main merge is
  the one step no session performs, so it is also the one step the plan cannot
  police: whoever merges gets whatever the repo's default button offers, and a
  default of "Squash and merge" silently collapses every stage into a single
  commit on `main`. The result looks successful — the PR is merged, the files
  are all there — and the per-stage history the non-squash merge exists to
  preserve is simply gone. It is easiest to hit from a phone, where the button
  is tapped without the dropdown ever being opened. Closeout states the
  required merge type in the final PR's body for exactly this reason, but a
  line in a PR body is a reminder, not a control.
- **The clone never leaves the plan branch.** *The clone holds the plan;
  worktrees hold the work.* A stage branch is checked out only in its own
  sibling worktree (`../<repo>-s<N>`), created at stage time from the plan
  branch tip and removed after its PR merges — so `.plan/` stays readable in
  the clone at every moment and the `done` write needs no checkout. If a
  stage worktree still holds uncommitted or unpushed work, it is left alone
  and reported rather than removed; the leftover is flagged by every later
  preflight, and closeout stops on it. A worktree that is merely *left over* —
  its branch merged, nothing unpushed — is cleared by closeout instead of
  blocking it.
- **A fresh worktree contains only tracked files.** Untracked local setup a
  stage needs (`.env`, local config, caches, dependency directories) has to be
  copied in — the stage does that and records what it copied in the ledger.
- Branch-per-stage and worktree-per-stage are the only supported model — both
  are recorded as frozen decisions at bootstrap, not choices offered at that
  time.

## 4. Review — the standing final stage

Bootstrap always appends `SF: plan review` (run with
`/plan-staged-rollout:stage-run f`, or by asking to "run the review stage").
It is the one stage exempt
from the read-scope rule: it reads the *entire* ledger — every note, gotcha,
shortcut, and known gap accumulated across all stages — and sweeps for
stragglers. Crucially, **it catalogs; it never implements.** Each finding
becomes exactly one of:

- **A new stage in this plan** — for follow-up work that belongs to this
  project (a shortcut to reconcile, a config to bring under management). It
  gets a PLAN.md stage index row (with its flags), a ledger row, and a stage
  file, and runs later as a normal `/plan-staged-rollout:stage-run <N>` in its
  own fresh session and branch, like any other stage.
- **A spin-off candidate** — for work that has outgrown this plan (a genuinely
  new project). It's recorded in the ledger and surfaced in the final PR body
  as follow-up work; it does not block closeout. Start it later with its own
  `/plan-staged-rollout:plan-stages`.
- **An explicit "accepted, won't fix"** — with a one-line reason, so the gap
  is a decision instead of a surprise.

Its acceptance check: every loose end in the notes is either a new ledger row
or explicitly closed.

## 5. Closeout — `/plan-close`

Refuses to run until every ledger row is `done` or `skipped` (including the
stages the review spawned) and `.plan/BLOCKED.md` holds no leftover `### S<N>`
section from a stage that was later resolved by hand — nothing clears that
file automatically, so closeout checks it instead of trusting the ledger
alone. Then it:

1. distills `PLAN.md` + the ledger into the final PR body, so the *why* and
   the as-built story survive on `main`;
2. clears the stage worktrees that are finished — merged branch, nothing
   unpushed — and stops on any that still holds work git cannot recover;
3. deletes `.plan/` as the last commit on the plan branch (nothing is lost —
   the full plan history remains in git; keeping it is the `plan-dir: keep`
   option, for a project where the plan doubles as documentation);
4. proposes the PR from `plan-<slug>` to `main`. You review and merge.

It runs headless too — `/plan-close --unattended` applies the plan flags
instead of asking, and a
[remotely driven plan](ON-THE-RUN.md#under-the-hood) can run it
as one more fired session once every stage is settled. Merging that final PR is
yours in every mode.
