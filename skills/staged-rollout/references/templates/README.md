# `.plan/` — <Project name>

Ledger-driven, one-stage-at-a-time rollout, built to run in **short,
low-context sessions you can pick up whenever you have time**. Each stage runs
in its own fresh session and lands as its own PR, so context never accumulates
and any single stage is easy to review or undo.

## How to run a stage

Start a **fresh** session and paste one line:

> Follow the instructions in `.plan/stage-<N>-<slug>.md`.

That's the whole prompt — the stage file points the session at the shared
protocol and frozen decisions in `PLAN.md`. If this repo has the
`plan-staged-rollout` plugin installed, asking to **"run stage \<N> of the
plan"** — or the explicit command `/plan-staged-rollout:plan-run <N>` — is
the same thing with ergonomics (it also runs the model/effort weight check
for you). The `.plan/` folder works standalone either way; the plugin is
convenience, not a dependency.

Run stages in any order allowed by their `depends`. The **runnable set** is
every `todo` row in `LEDGER.md` whose dependencies are all `done` or
`skipped` — often more than one. Stages in that set do not depend on each
other, so you can run them
**concurrently, one per fresh session** (one terminal each) — each one works
in its own worktree, so they never collide. `PLAN.md`'s *Runnable set & waves*
defines the set and shows how waves and the critical path are derived from the
`Depends` column — they are never stored as a column of their own.

<!-- If a strict majority of stages in PLAN.md's stage index share a `model`,
bootstrap fills in a line here, e.g.: "6 of 8 stages recommend `opus` —
setting it as your session default means the weight gate only prompts on the
exceptions." Delete this comment (and the line above, if bootstrap didn't add
one) once filled. -->

## Files

- `PLAN.md` — architecture, **frozen decisions**, stage index, and the
  operating protocol every stage session follows. Single source of truth for
  decisions; changed only when a decision changes.
- `LEDGER.md` — status table + per-stage as-built notes. The tracker that
  changes as you execute; the resume point and cross-session memory.
- `stage-<N>-<slug>.md` — one small, self-contained stage each.
- `BLOCKED.md` — only present after an unattended driver ran out of attempts
  on a stage: the driver's own block record and runbook, kept out of
  `LEDGER.md` so it never collides with a stage branch's unmerged ledger
  edits. Delete a stage's section there once that stage is resolved.

## Git & worktree model

```
main
 └── plan-<slug>                    ← plan branch; .plan/ lives here
      ├── plan-<slug>-s0  → PR → plan-<slug>
      ├── plan-<slug>-s1  → PR → plan-<slug>
      └── ...
plan-<slug> → final PR → main       ← at /plan-close
```

**The clone holds the plan; worktrees hold the work.** This clone stays on
`plan-<slug>` for the whole plan — that is the only branch checked out here,
which is why `.plan/` is always in front of you. Each stage branch is checked
out only in its own sibling directory, created when the stage starts and
removed once its PR merges:

```
../<repo>-s1/     ← worktree, branch plan-<slug>-s1
../<repo>-s3/     ← worktree, branch plan-<slug>-s3   (running concurrently)
```

A fresh worktree has only tracked files, so a stage that needs untracked local
setup (`.env`, local config, caches) copies it in and says so in the ledger. A
worktree with uncommitted or unpushed work is never removed automatically — it
is reported, shows up in every later preflight, and blocks closeout.

`.plan/` is **tracked** on the plan branch, and the plan branch is pushed with
an upstream. Don't add `.plan/` to `.gitignore`: an untracked plan can't
produce the per-stage commits and PRs this model runs on, and a local-only
plan branch makes each session's sync a silent no-op.

When two stages run at once, nothing above changes — there are simply two
stage branches open in two worktrees, both cut from the same plan-branch tip.
The plan branch is the serialization point: their PRs merge one at a time, and whoever merges
second first merges the plan branch into their stage branch and re-runs the
stage's acceptance check. `PLAN.md`'s *Concurrent stages* has the full rules,
including the one race worth knowing about — the `done` ledger write is a
direct commit on the plan branch, so it is made after the fast-forward and
replayed (never force-pushed) if a sibling wins.

Every stage gets its own branch and PR into the plan branch — the only
supported model, fixed at bootstrap. Branch names are flat (`plan-<slug>-s3`,
not `plan/<slug>/s3`) because git refs can't nest a branch under an existing
branch name. Commits on a stage branch are compulsory and incremental —
logical units as the stage progresses, not one commit at the end. Branch
creation and pushes are autonomous on feature branches — the agent creates
and pushes stage/plan branches without asking, and opens the stage PR as a
compulsory part of finishing a stage; merges are offered and happen only on
your OK, and it never pushes to `main`. The one carve-out is `merge: auto` on
`PLAN.md`'s plan flags line: that is your OK given in advance for **stage PRs
only**, so the session squash-merges its own stage PR once checks are green —
the plan→main PR is yours in every mode. A stage cannot be marked `done` until
its PR is merged into the plan branch. Stage PRs are squash-merged into the
plan branch; the final PR from the plan branch into `main` is a normal
(non-squash) merge, so each stage keeps its own commit on `main`. This needs
the GitHub repo to allow both squash merging and merge commits (recommended:
squash message = "Pull request title and commit details", merge-commit
message = "Pull request title and description").

## Closeout

When every ledger row is `done` or `skipped`, close out the plan — ask to
**"close out the plan"**, or run the explicit command
`/plan-staged-rollout:plan-close`, which is where the closeout steps live. It
distills `PLAN.md` + the ledger into the final PR body, removes any stage
worktree that is merged and fully pushed (anything holding unpushed work stops
it instead), deletes `.plan/` as the last commit — or keeps it, per the
`plan-dir` flag on `PLAN.md`'s plan flags line — and proposes the PR from
`plan-<slug>` to `main`.

**Closeout runs unattended too:** `/plan-staged-rollout:plan-close
--unattended` applies the plan flags instead of asking and opens the PR.
Merging that PR into `main` is always a person's job, in every mode.
