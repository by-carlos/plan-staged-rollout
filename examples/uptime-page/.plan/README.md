# `.plan/` — Uptime page

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

Run stages in any order allowed by their `depends`. The next runnable stage is
the first `todo` row in `LEDGER.md` whose dependencies are all `done`.

3 of 4 stages recommend `sonnet` — setting it as your session default means
the weight gate only prompts on the exceptions.

## Files

- `PLAN.md` — architecture, **frozen decisions**, stage index, and the
  operating protocol every stage session follows. Single source of truth for
  decisions; changed only when a decision changes.
- `LEDGER.md` — status table + per-stage as-built notes. The tracker that
  changes as you execute; the resume point and cross-session memory.
- `stage-<N>-<slug>.md` — one small, self-contained stage each.

## Git model

```
main
 └── plan-uptime-page                    ← plan branch; .plan/ lives here
      ├── plan-uptime-page-s0  → PR → plan-uptime-page
      ├── plan-uptime-page-s1  → PR → plan-uptime-page
      └── ...
plan-uptime-page → final PR → main       ← at /plan-close
```

Every stage gets its own branch and PR into the plan branch — the only
supported model, fixed at bootstrap. Branch names are flat
(`plan-uptime-page-s2`, not `plan/uptime-page/s2`) because git refs can't
nest a branch under an existing branch name. Commits on a stage branch are
compulsory and incremental — logical units as the stage progresses, not one
commit at the end. Branch creation and pushes are autonomous on feature
branches — the agent creates and pushes stage/plan branches without asking,
and opens the stage PR as a compulsory part of finishing a stage; merges are
offered and happen only on your OK, and it never pushes to `main`. A stage
cannot be marked `done` until its PR is merged into the plan branch. Stage
PRs are squash-merged into the plan branch; the final PR from the plan branch
into `main` is a normal (non-squash) merge, so each stage keeps its own
commit on `main`. This needs the GitHub repo to allow both squash merging and
merge commits (recommended: squash message = "Pull request title and commit
details", merge-commit message = "Pull request title and description").

## Closeout

When every ledger row is `done` or `skipped`, close out the plan — ask to
**"close out the plan"**, run the explicit command
`/plan-staged-rollout:plan-close`, or follow the closeout steps in `PLAN.md`
directly: it distills `PLAN.md` + the ledger into the final PR body, deletes
`.plan/` as the last commit (keeping it is an option), and proposes the PR
from `plan-uptime-page` to `main`.
