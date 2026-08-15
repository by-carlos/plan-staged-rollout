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
about itself. Maintain this tier list as model families evolve:

- **Top tier ("Opus-class"):** the Opus generation (e.g. `claude-opus-*`).
- **Mid tier ("Sonnet-class"):** the Sonnet generation (e.g. `claude-sonnet-*`),
  and equivalently-positioned mid-tier models (e.g. `claude-fable-*`).
- **Light tier ("Haiku-class"):** the Haiku generation (e.g. `claude-haiku-*`).

**Fail-safe:** if the session's disclosed model ID or name doesn't recognizably
match a tier above — an unfamiliar family, a third-party model, a future rename —
do not guess which tier it belongs to. State the exact model ID/name from the
system prompt and ask the user which tier applies, rather than silently passing
or failing the gate.

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

**Branch-per-stage is the only supported model** — it's the model this plugin
was built with, and there is no alternative to choose at bootstrap:

```
main
 └── plan-<slug>                      ← plan branch; .plan/ lives here
      ├── plan-<slug>-s0 → PR → plan-<slug>   (squash merge)
      ├── plan-<slug>-s1 → PR → plan-<slug>   (squash merge)
      └── ...
plan-<slug> → final PR → main         ← at closeout (normal merge)
```

Six frozen semantics:

1. **One branch per stage**, cut from the plan branch (`plan-<slug>`) — no
   exceptions. Uniformity keeps each unit reviewable in isolation and contains
   the classic failure where "one small commit" quietly becomes twenty commits
   of fixes bleeding into shared history.
2. **Commits are compulsory and incremental** — commit at logical units as the
   stage progresses, not a single commit at stage end.
3. **A stage PR into the plan branch is compulsory** — the finish protocol
   creates it; it is never "offered" as optional.
4. **A stage cannot be closed (marked `done`) until its PR is merged** into
   the plan branch.
5. **After the merge, check out the plan branch and fast-forward** before the
   session ends — and record the stage `done` in the ledger there: the `done`
   edit is committed on the plan branch after the merge, never on the stage
   branch, so a `done` row is always visible from a synced plan branch.
6. **Merge type is fixed by position:** each stage PR is **squash-merged** into
   the plan branch (one clean commit per stage, no intra-stage churn on the plan
   branch); the final PR from the plan branch into `main` is a **normal
   (non-squash) merge**, so every stage lands on `main` as its own distinct
   commit and the as-built history survives.

Also: **flat branch names** (`plan-<slug>-s3`, not `plan/<slug>/s3`) — git
refs can't nest a branch under an existing branch name. And **push freely,
offer merges**: stage and plan branches are feature branches — the agent
creates and **pushes** them without asking, and **opens** the stage PR into
the plan branch as part of the compulsory finish protocol, but **offers** the
merge for your OK — it never merges without your OK, never pushes to `main`,
and the final PR to `main` is always yours to merge.

**Preflight & sync — verify git state before trusting the ledger.** The
ledger is canonical, but only after it's proven fresh: every stage session
and the closeout start with a preflight block, defined once in the template
`PLAN.md`'s operating protocol — fetch, fast-forward the plan branch (holds
under both squash-merge and merge-commit remotes), require a clean tree and
a sane HEAD position, and reconcile the ledger rows against actual branch
and PR state. One state is self-healing (a `doing` row whose PR merged
remotely gets its `done` recorded); everything else is drift, and the
preflight **reports and stops** — it never auto-stashes, resets, or deletes
branches.

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
