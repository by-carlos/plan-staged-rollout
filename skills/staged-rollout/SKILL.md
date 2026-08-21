---
name: staged-rollout
description: Use when a build is too big for one session and must be run as many small, resumable sessions — a staged or milestone rollout with cross-session progress tracking, a persistent plan that must not drift, and stop/resume freely over hours or days. Covers decomposing a large project into a `.plan/` folder of dependency-ordered stages with an evidence ledger, and executing one stage per fresh session. NOT for single-session tasks, quick fixes, or work of roughly three sessions or less — the scaffold has a floor cost that only pays off on genuinely large, decomposable builds.
---

# Staged rollout

Run a large build as **many small sessions, not one huge one.** Decompose the
work once into dependency-ordered stages in a `.plan/` folder, then execute one
stage per fresh session. Context can't accumulate across stages because sessions
don't share it; the plan can't drift because every decision lives in exactly one
place; progress is a glanceable ledger, not a transcript.

The file formats are in `references/templates/` (`PLAN.md`, `LEDGER.md`,
`stage-N.md`, `stage-f-review.md`, `README.md`) — copy those verbatim for
structure, then fill every `<placeholder>` when scaffolding. This file is the
*method*: when to use it, how to decompose, how to set flags. Don't restate
the templates here.

## When to use it

All of these true: the work spans multiple sessions (hours/days, roughly four+
sessions of work); it decomposes into ordered units with dependencies; you want
to stop and resume freely; you care about keeping per-session token cost flat;
and the design is settle-able (there are decisions worth freezing).

## When NOT to use it

- **Work that fits in one to three sessions.** The scaffold has a floor cost;
  below ~four sessions, just do the work.
- **Exploratory work with no settle-able design.** If every session would
  legitimately rewrite the frozen decisions, there's nothing to freeze yet.
- **Work that can't be decomposed.** One giant inseparable step gains nothing
  from a ledger around it.

Two honest limits even when it fits: decomposition quality gates everything (bad
stage boundaries cause cross-stage churn no protocol fixes — the final review
stage catches what leaks, but it can't un-tangle a bad split); and fresh
sessions only know what was written down (note discipline replaces the tacit
context a long session would carry).

## Core principles

1. **Single source of truth, referenced not copied.** All durable decisions live
   in `PLAN.md` as *frozen decisions*. Stage files and prompts point at it; they
   never restate it. Copies are what drift — a decision that exists in one place
   cannot diverge.
2. **Session-per-stage = free context control.** The primary token-control
   mechanism isn't subagents or clever prompting — it's that each stage is small
   and runs in its own fresh session. Cost per stage is flat
   (`O(PLAN.md + stage file + ledger table)`), no matter how many stages came
   before. No compaction spiral.
3. **The ledger is the resume point *and* the memory.** `LEDGER.md` holds
   per-stage status plus as-built notes, so "where were we?" is a 10-line table,
   and a later stage can catch a regression an earlier one introduced because the
   earlier stage's assumptions were written down.
4. **Verify before done.** A stage is done when its acceptance check *ran* and
   the real output is pasted into the ledger — not when the model claims success.
   Evidence, not assertion.

## Decomposing the work

- **Smallest sensible stage.** If a unit has two genuinely different mechanisms,
  or a design-heavy part plus mechanical parts, split it.
- **Group by effort, not just by feature.** Several near-identical mechanical
  units can be one stage; a single design-heavy unit deserves its own.
- **Keystone as S0.** Identify the piece with no prerequisites that everything
  else needs, make it S0, and gate the rest behind it.
- **`depends` is a graph, not a queue.** An edge means "cannot safely start
  until", not "written after". Serialising by habit — writing
  `S0 → S1 → S2 → S3` where the truth is `S0 → {S1, S2, S3}` — is the most
  expensive decomposition mistake available here, because the index still
  reads as correct while the plan takes three rounds instead of two. For every
  edge, name the artifact the dependent stage consumes; if you can't name one,
  drop the edge.
- **Standing final review stage.** Always append `SF: plan review` as the last
  stage (see below), scaffolded from `stage-f-review.md`. Bootstrap adds it;
  it's not optional.

## Flag heuristics

Each stage declares `depends` / `mode` / `exec` / `model` / `effort` in the
**PLAN.md stage index** — the single authoritative home for these flags, read
by `/plan-run`'s weight check and next-runnable logic. Stage files never restate
them. Defaults are deliberately cheap — escalate only where a stage genuinely
warrants it:

- `mode: direct` by default (state a one-line plan, implement). Use `brainstorm`
  only where the stage has real open design choices. A full brainstorm on a
  mechanical one-liner is pure ceremony.
- `exec: inline` by default. Session-per-stage already isolates context, so
  reserve `subagent(<model>)` for churn-heavy stages (lots of iteration, config,
  debugging) where dispatching keeps the churn out of the orchestrator's context.
- `model`/`effort` are **launch hints**, not switches the agent can flip
  mid-session. The model is verifiable from the session; effort is a reminder
  (not introspectable — never claim to verify it). Default to the cheaper capable
  model; reserve the top model for the keystone and the one or two design-heavy
  stages. Most staged work is `low`/`med` effort.

## Model weight tiers

Every weight check (bootstrap's gate, a stage's `model` comparison) needs a
mechanical rule for "is this session heavy enough" — not the model's own guess
about itself. Maintain this tier list as model families evolve, and place a new
family by its capability and price, not by where its name sorts:

- **Top tier ("Opus-class"):** the Opus generation (e.g. `claude-opus-*`), plus
  any frontier family positioned at or above it (e.g. `claude-fable-*`).
- **Mid tier ("Sonnet-class"):** the Sonnet generation (e.g. `claude-sonnet-*`).
- **Light tier ("Haiku-class"):** the Haiku generation (e.g. `claude-haiku-*`).

**Fail-safe:** if the session's disclosed model ID or name doesn't recognizably
match a tier above — an unfamiliar family, a third-party model, a future rename —
do not guess which tier it belongs to. State the exact model ID/name from the
system prompt and ask the user which tier applies, rather than silently passing
or failing the gate.

## Parallel stages

`depends` is a real dependency graph, so more than one stage is often runnable
at once. Three rules keep that an advantage rather than a source of confusion:

- **Derive, never store.** The runnable set, the waves, and the critical path
  are *views* of the `depends` column, computed on demand — by bootstrap's
  post-decomposition summary and by every stage's end announcement. Do **not**
  add a `wave` or `parallel-group` column to the stage index: that would be a
  second copy of the graph, and principle 1 exists precisely because copies
  drift.
- **Report the set; don't launch it.** The deliverable is telling the operator
  what *can* overlap — every `todo` stage whose `depends` are all `done`, each
  with its command and recommended model/effort. Starting them is the
  operator's action, one session per stage: a session cannot spawn independent
  top-level sessions, and nothing in this method pretends otherwise.
- **Separate working trees are what make it physical.** The semantics below
  make concurrent sessions *safe*; worktree-per-stage (see *Git model*) makes
  them *possible*. Two sessions sharing one working tree fight over `HEAD`
  whatever the merge rules say.

Four semantics are what make concurrent sessions safe rather than merely
possible. They are specified in full in the template `PLAN.md`, which owns the
operating protocol; the reasoning behind them is the method:

- **The plan branch is the serialization point.** Parallel stage PRs merge one
  at a time, first come first served. The second merger syncs the plan branch
  *into* its stage branch and re-runs the acceptance check — "mergeable" means
  no textual conflict, not that the stage still passes. Squash merge makes
  that free (the merge commit is discarded), which is why a stage branch is
  never rebased or force-pushed.
- **A sibling's stage branch is not drift.** Preflight classifies by *whose*
  stage a mismatch belongs to instead of halting on any `todo` row with a
  committed branch — otherwise every parallel session stops the moment a
  second one starts. Real drift on the stage you are running still stops you,
  and a genuinely crashed stage stays visible in every later preflight report
  and in closeout's gate.
- **Shared write territory is a `depends` edge, not a new field.** Two stages
  that write the same files are not independent, whatever the feature graph
  says, and `depends` is the only place that can say so. A dedicated
  "territory" field would be a second record of one constraint — a second
  thing to drift.
- **The `done` ledger write races.** It is a direct commit on the plan branch,
  so two sessions finishing together collide there: replay the commit on
  rejection, keep both rows on conflict, never force-push the plan branch.

**Is `exec: subagent(<model>)` fan-out an alternative to parallel sessions?**
Only *inside* a stage — never as a substitute for them. Dispatching a whole
wave from one orchestrator does sidestep git concurrency, but it collapses N
stages into one: a single branch, PR, ledger row, and acceptance check
covering work the decomposition deliberately kept separate (git semantics 1
and 3) — and the orchestrator accumulates every subagent's return, so
per-session cost stops being flat and principle 2, the mechanism the whole
method rests on, goes with it. For a wave of cheap mechanical stages the
honest options are therefore: run them as N sessions (the supported answer),
or decide at **decomposition** time that they were really one stage, merge
them, and let `exec: subagent(<model>)` absorb the churn within it. That is a
decomposition decision, not an execution one — "group by effort, not just by
feature" already points at it.

## Statuses and human-gated stages

Statuses are `todo → doing → done`, plus `blocked` and `skipped` (full lifecycle
and the checkbox resume mechanism are in the templates). Two are worth calling
out as method, not just vocabulary:

- **`blocked`** is a first-class state, not a failure. A stage that hits a gate
  only a human or an external system can clear (a GUI-only action, a credential,
  an approval) is best written as a **runbook**: produce exact step-by-step
  instructions plus the verification check, mark the stage `blocked`/`doing`, and
  let the human complete it. Never fake progress past a gate.
- **`skipped`** records a one-line reason for work decided against, so the gap is
  a decision, not a silent hole.

Track known gaps and latent hazards explicitly in the ledger notes (things not
under version control, footguns, "this script would delete X if run") — writing
them down is what stops them becoming surprises, and it's what lets the final
review stage catch them.

## Git model

**Branch-per-stage in a worktree-per-stage is the only supported model** —
it's the model this plugin was built with, and there is no alternative to
choose at bootstrap:

```
main
 └── plan-<slug>                      ← plan branch; .plan/ lives here
      ├── plan-<slug>-s0 → PR → plan-<slug>   (squash merge)
      ├── plan-<slug>-s1 → PR → plan-<slug>   (squash merge)
      └── ...
plan-<slug> → final PR → main         ← at closeout (normal merge)
```

**`.plan/` must be tracked, and the plan branch must have an upstream.** Both
are load-bearing invariants, not tidiness. An untracked (or `.gitignore`d)
`.plan/` breaks the model in two ways at once: a stage whose only artifacts are
decisions or documentation produces nothing to commit, so it can never open the
PR that semantics 3–4 below require, and every stage depending on it deadlocks
on an unsatisfiable gate; and the whole decision record lives only in a working
directory that a `git clean` or a deleted worktree takes with it. A local-only
plan branch is the quieter version of the same failure — the preflight's fetch
and fast-forward both succeed and do nothing, forever. Bootstrap refuses to
scaffold into an ignored path and pushes the plan branch with an upstream;
every stage preflight re-checks both.

Seven frozen semantics:

1. **One branch per stage**, cut from the plan branch (`plan-<slug>`) — no
   exceptions. Uniformity keeps each unit reviewable in isolation and contains
   the classic failure where "one small commit" quietly becomes twenty commits
   of fixes bleeding into shared history.
2. **Commits are compulsory and incremental** — commit at logical units as the
   stage progresses, not a single commit at stage end. Every stage has
   something to commit: the ledger evidence and any frozen-decision amendment
   are tracked files, so even a decision-only stage lands a real commit and a
   real PR.
3. **A stage PR into the plan branch is compulsory** — the finish protocol
   creates it; it is never "offered" as optional.
4. **A stage cannot be closed (marked `done`) until its PR is merged** into
   the plan branch.
5. **After the merge, return to the clone and fast-forward** the plan branch
   before the session ends — the clone is already on it, so there is no
   checkout — and record the stage `done` in the ledger there: the `done`
   edit is committed on the plan branch after the merge, never on the stage
   branch, so a `done` row is always visible from a synced plan branch.
6. **Merge type is fixed by position:** each stage PR is **squash-merged** into
   the plan branch (one clean commit per stage, no intra-stage churn on the plan
   branch); the final PR from the plan branch into `main` is a **normal
   (non-squash) merge**, so every stage lands on `main` as its own distinct
   commit and the as-built history survives.
7. **One worktree per stage, and the clone never leaves the plan branch.** A
   stage branch is checked out only in its own sibling worktree
   (`../<repo>-s<N>`); the main clone stays parked on `plan-<slug>` for the
   life of the plan. See *Worktree-per-stage* below.

Also: **flat branch names** (`plan-<slug>-s3`, not `plan/<slug>/s3`) — git
refs can't nest a branch under an existing branch name. And **push freely,
offer merges**: stage and plan branches are feature branches — the agent
creates and **pushes** them without asking, and **opens** the stage PR into
the plan branch as part of the compulsory finish protocol, but **offers** the
merge for your OK — it never merges without your OK, never pushes to `main`,
and the final PR to `main` is always yours to merge.

### Worktree-per-stage

**The clone holds the plan; worktrees hold the work.** The main clone is
permanently parked on `plan-<slug>` — that is the only branch ever checked out
there. Every stage branch lives in its own sibling worktree, created from the
plan branch tip:

```
~/src/
  hive/        ← main clone, always on plan-<slug>, holds .plan/
  hive-s1/     ← worktree, branch plan-<slug>-s1
  hive-s3/     ← worktree, branch plan-<slug>-s3   (concurrent)
```

This is fixed, not a choice — the same register as branch-per-stage. Three
things follow from it, and they are why it is worth a frozen semantic rather
than a suggestion:

- **The ledger is always readable and always writable.** Because the clone
  never moves off the plan branch, `.plan/` there is the synced plan-branch
  copy at every moment. The `done` write (finish step 5) is a commit in the
  clone that needs no checkout and cannot disturb an in-flight stage.
- **Concurrency stops contending for `HEAD`.** *Parallel stages* above makes
  concurrent sessions semantically safe; separate working trees are what make
  them physically possible. Two sessions in one directory fight over the
  checkout no matter how correct the merge rules are.
- **Provisioning prefers the harness, falls back to git.** Use the harness's
  native worktree mechanism when there is one (Claude Code's `EnterWorktree`,
  or `superpowers:using-git-worktrees` when installed); otherwise
  `git worktree add`. What it must **never** do is degrade to checking the
  stage branch out in the clone — if the harness refuses to work outside its
  original directory, the honest move is to stop and hand the operator the
  path to relaunch in.

Two honest costs, named where they bite rather than discovered later. A fresh
worktree contains only tracked files, so untracked local setup a stage needs
(`.env`, local config, build caches, `node_modules`) is not there — copy what
the stage needs and note it in the ledger. And a worktree is a real directory
that outlives a crashed session, so teardown is part of the protocol: after
the merge, a clean and fully-pushed worktree is removed along with its merged
branch, while anything uncommitted, unpushed, or stashed is left alone and
reported. Preflight reports orphans; closeout refuses to run while one
survives.

**Preflight & sync — verify git state before trusting the ledger.** The
ledger is canonical, but only after it's proven fresh: every stage session
and the closeout start with a preflight block, defined once in the template
`PLAN.md`'s operating protocol — confirm `.plan/` is tracked and the plan
branch has an upstream, fetch, fast-forward the plan branch (holds
under both squash-merge and merge-commit remotes), require a clean tree in
both the clone and this worktree, apply the **two-tree rule** to HEAD (the
clone on the plan branch, the stage on its own worktree), and reconcile the
ledger rows against actual branch, PR, and worktree state. One state is self-healing (a `doing` row whose PR merged
remotely gets its `done` recorded); one is expected under concurrency (another
stage's in-flight branch — reported, not fatal, see *Parallel stages*);
everything else is drift, and the preflight **reports and stops** — it never
auto-stashes, resets, or deletes branches.

## The final review stage

`SF` is the one stage exempt from the read-scope rule: it reads the *entire*
ledger — every note, gotcha, shortcut, and known gap — and sweeps for stragglers.
Crucially, **it catalogs; it never implements.** Each finding becomes exactly one
of three outcomes:

- **A new stage in this plan** — follow-up work belonging to this project. It
  gets a **PLAN.md stage index row** (with its flags — required, since the weight
  check and next-runnable logic only see stages listed in the index), a ledger
  row, and a stage file, and runs later as a normal stage in its own fresh
  session and branch.
- **A spin-off candidate** — work that has outgrown this plan (a genuinely new
  project). Recorded in the ledger and surfaced in the final PR body as follow-up;
  it does *not* block closeout. Start it later with its own bootstrap.
- **An explicit "accepted, won't fix"** — with a one-line reason, so the gap is a
  decision instead of a surprise.

Its acceptance check: every loose end in the notes is either a new stage (a
stage index row, a ledger row, and a stage file) or explicitly closed.

## Closeout

Closeout refuses to run until every ledger row is `done` or `skipped` (including
stages the review spawned) **and** no stage PR into the plan branch remains
open or unmerged — a `done` row alone is not enough; the preflight's
reconcile runs first and treats that mismatch as a gate failure. Then it: distills `PLAN.md` + the ledger into the
final PR body so the *why* and the as-built story survive on `main`; deletes
`.plan/` as the last commit on the plan branch (nothing is lost — the full plan
history remains in git; keeping `.plan/` is an offered option where the plan
doubles as documentation); and proposes the PR from `plan-<slug>` to `main` for
the human to review and merge.

## Anti-patterns this exists to prevent

- Restating decisions in prompts or stage files — copies drift; point at
  `PLAN.md`.
- One giant stage — blows context, can't resume; split it.
- Brainstorming everything — design ceremony on mechanical work; `direct` is the
  default.
- Subagents everywhere — session-per-stage already isolates context; reserve them
  for churn.
- Claiming done without evidence — the acceptance output must actually land in
  the ledger.
- Silent scope creep — "while I'm here…"; note it, spin a stage, move on.
- Editing decisions in two places — frozen decisions change in `PLAN.md` only.
- Skipping the dependency gate — building on an unbuilt prerequisite.
- Checking a stage branch out in the main clone — the clone is the plan's
  window; moving it hides the ledger and breaks every concurrent session.
