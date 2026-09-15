# slugify — plan & protocol

A deliberately small Python library: turn an arbitrary string into a URL-safe
slug, with a console entry point. Stdlib only, no runtime dependencies. The
library is not the point — it exists so that an **"on the run"** proof of
concept has real edits to make, real tests to run and real pull requests to
open, on a throwaway repository. See
[`../README.md`](../README.md) for how this plan is driven.

This file is the **single source of truth** for durable decisions: the
architecture, the frozen decisions, the stage index, and the operating
protocol every stage session follows. Decisions live here and are *referenced,
never copied*.

## Architecture (what we're building)

```
slugify/
  core.py          # slugify(text, *, max_length=None) -> str
  cli.py           # console entry point: slugify [--max-length N] TEXT...
tests/
  test_core.py
  test_cli.py
pyproject.toml     # packaging + console-script entry point (no runtime deps)
LICENSE            # chosen by the maintainer in S2 — not by a stage runner
scripts/
  verify_run.py    # the run's own pass/fail command (copied in at setup)
.plan/
  verify-manifest.json  # what SF's verification asserts
  pr-states.json        # PR state captured from the GitHub MCP server by SF
```

## Frozen decisions

Change these in THIS file only — never restate them in stage files or the
ledger.

- **Python 3.12, stdlib only at runtime** — `unicodedata` for normalisation,
  `re` for the character classes, `argparse` for the CLI. `pytest` is a
  dev-only dependency.
- **`slugify(text, *, max_length=None)`** NFKD-normalises, drops combining
  marks, lowercases, replaces every run of non-alphanumerics with a single
  `-`, and strips leading/trailing `-`. Empty input and input that reduces to
  nothing both return `""` — never an exception. `max_length` truncates at a
  `-` boundary where one exists within the limit, never mid-word.
- **The CLI** joins its positional arguments with a space, prints the slug,
  and exits `0`; an empty result prints nothing and exits `1`.
- **Git strategy:** branch-per-stage. `.plan/` is **tracked** on the plan
  branch and the plan branch has an **upstream**. `main` → `plan-slugify` (the
  plan branch; `.plan/` lives here) → one branch per stage
  `plan-slugify-s<N>`, each landing as a **squash-merged** PR into
  `plan-slugify`; the final PR `plan-slugify` → `main` at closeout is a
  **normal (non-squash) merge**. A stage cannot be marked `done` until its PR
  is merged into the plan branch; the `done` edit is committed on the plan
  branch *after* the merge.
- **The plan-to-main merge is the maintainer's, by hand.** No stage runner and
  no orchestrator performs it — that is a fixed condition of this proof of
  concept, not a preference.
- **Pass/fail is a command, not a transcript.** `scripts/verify_run.py`
  decides whether the run worked. SF runs it and pastes its output as
  evidence; nothing else counts as the result.
- **Worktree strategy:** worktree-per-stage. The clone stays parked on
  `plan-slugify`; each stage branch is checked out only in its own sibling
  worktree `../slugify-s<N>`.
- **Final review stage:** the last stage (`SF`) is the closeout — it runs the
  verification script and catalogs loose ends, and NEVER implements.

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort | gate |
|---|---|---|---|---|---|---|---|
| S0 Slug core | `stage-0-core.md` | — | direct | inline | opus | high | auto |
| S1 CLI | `stage-1-cli.md` | S0 | direct | inline | sonnet | med | auto |
| S2 License choice | `stage-2-license.md` | S0 | direct | inline | sonnet | med | human |
| SF Closeout | `stage-f-closeout.md` | S1, S2 | direct | inline | sonnet | med | auto |

Plan flags: `merge: auto` · `plan-dir: keep`

`merge: auto` is a **precondition of driving this plan from a phone**, not a
style choice: under `merge: manual` a fired stage never reaches `done`, so the
ledger never settles and the orchestrator cannot tell a finished stage from
one that never ran. `plan-dir: keep` keeps the ledger, the manifest and the
captured PR states on `main` after the final merge, so the run stays auditable
after the fact.

S2's `gate: human` is the point of the exercise, and it must exercise the
**whole** path: the orchestrator refuses to fire it and reports that it has;
the maintainer runs S2 interactively; the orchestrator then resumes and
carries on to SF. A run that only proves the refusal has proved half of it.

Flag values: `mode` = `direct` \| `brainstorm`; `exec` = `inline` \|
`subagent(<model>)`; `model`/`effort` = launch hints (checked, not faked);
`gate` = `auto` \| `human` (may the stage be launched with nobody watching? —
`human` means never); `merge` = `manual` \| `auto`; `plan-dir` = `delete` \|
`keep`.

## Runnable set

A stage is runnable when its row is `todo` and every stage in its `depends`
column is `done` or `skipped`. S0 is runnable immediately; S1 and S2 become
runnable together once S0 is done, and S2 is never fired unattended whatever
its row says; SF becomes runnable once both S1 and S2 have settled.

## Operating protocol

Every stage session, whether fired as a cloud routine or run interactively,
follows this. It is written to stand alone — a session that has never seen the
`plan-staged-rollout` plugin can follow it from this file.

**Preflight**

0.0 Confirm `.plan/` is tracked on the plan branch and the plan branch has an
    upstream. Both are load-bearing.
0.1 Read this file, then `.plan/LEDGER.md`'s status table, then the notes
    blocks of the stages this one `depends` on — and nothing else.
0.2 Check the session's model and effort against this stage's row in the stage
    index. A session lighter than the row asks for records the mismatch and
    marks the row `blocked` rather than doing the work under-weight.
0.3 If this stage's `gate` is `human` and nobody is watching, stop. Do not
    start the work.

**Work**

1. Flip the stage's ledger row to `doing` on the plan branch and push, before
   any work begins.
2. Create the stage branch from the plan branch tip in its own worktree, and
   push it immediately — before the work, so an interrupted stage is still
   visible.
3. Work the stage file's steps in order, ticking each box as it lands.
   Commits are compulsory and incremental — logical units as the stage
   progresses, not one commit at the end.
4. Run the stage's acceptance checks and capture their real output.

**Finish**

1. Push the stage branch.
2. Open the stage's pull request into the plan branch. Opening it is
   compulsory; it is how the stage ends.
3. Under `merge: auto`, squash-merge that pull request once its checks are
   green. Never merge into `main`.
4. Record the pull request number, and its merged state, where the ledger's
   notes block for this stage can carry it.
5. On the plan branch — *after* the merge — flip the row to `done`, paste the
   acceptance output as evidence in the notes block, add an as-built note and
   any gotcha the later stages need, and push. The pushed ledger row is the
   only completion signal anything outside the session can see.
6. Remove the stage worktree if it is clean and fully pushed; leave it and
   report otherwise.

**If the stage cannot finish**

Leave the row at `doing` with a handoff note saying exactly what is done and
where to resume, or set it to `blocked` and write `.plan/BLOCKED.md` as a
runbook for the person who has to unblock it. Never mark a stage `done` on the
strength of intent.
