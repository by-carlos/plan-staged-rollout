# Uptime page — plan & protocol

A tiny status-page generator: check a configured list of URLs and publish the
results as a single static HTML page, suitable for a cron job or CI schedule.
No server, no JavaScript, no third-party runtime dependencies. This file is
the **single source of truth** for durable decisions: the architecture, the
frozen decisions, the stage index, and the operating protocol every stage
session follows. Decisions live here and are *referenced, never copied* — a
decision that exists in one place cannot diverge.

## Architecture (what we're building)

```
uptime/
  checker.py       # load_config(path) + run_checks(config) -> list[CheckResult]
  cli.py           # console entry point: uptime-page [--config PATH] [--write-page]
  render.py        # render(results) -> HTML; write_page(results, path)
checks.toml        # [[check]] array: name, url, optional timeout_s
tests/
  test_checker.py
  test_cli.py
  test_render.py
pyproject.toml     # packaging + console-script entry point (no runtime deps)
public/
  index.html       # the generated artifact — written by the tool, not by hand
```

## Frozen decisions

Change these in THIS file only — never restate them in stage files or the
ledger. If a stage changes a decision, amend it here as the last step of that
stage (Operating protocol, finish step 3).

- **Python 3.12, stdlib only at runtime** — `urllib.request` for the checks,
  `tomllib` for config, `string.Template` for HTML. `pytest` is a dev-only
  dependency.
- **Config is `checks.toml`:** a `[[check]]` array with `name`, `url`, and
  optional `timeout_s` (default 5). Invalid entries raise `ConfigError`
  naming the offending key.
- **A check passes iff** the HTTP status is 2xx/3xx within its timeout.
  `run_checks` never raises on a failing check — network errors come back as
  `ok=False, status=None`. All timestamps are UTC ISO-8601.
- **Output is a single static `public/index.html`** — no server, no JS.
- **Git strategy:** branch-per-stage (fixed — the only supported model).
  `main` → `plan-uptime-page` (the plan branch; `.plan/` lives here) → one
  branch per stage `plan-uptime-page-s<N>` (flat names — git refs can't nest
  a branch under an existing branch), each landing as a **squash-merged** PR
  into `plan-uptime-page`; final PR `plan-uptime-page` → `main` at closeout
  is a **normal (non-squash) merge** so each stage keeps its own commit on
  `main`. Commits on a stage branch are compulsory and incremental (logical
  units as the stage progresses, not one commit at the end). The agent
  creates and pushes stage and plan branches without asking, and **opens**
  the stage PR as a compulsory part of finishing a stage — never merging
  without your OK, never pushing to `main`. A stage cannot be marked `done`
  until its PR is merged into the plan branch; the `done` edit itself is
  committed on the plan branch *after* the merge (Operating protocol, finish
  step 5), never on the stage branch.
- **Final review stage:** the last stage (`SF`) is a standing plan review. It
  catalogs loose ends — each becomes a new in-plan stage, a spin-off
  candidate, or an explicit "accepted, won't fix" — and NEVER implements.

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort |
|---|---|---|---|---|---|---|
| S0 Checker core | `stage-0-checker-core.md` | — | direct | inline | opus | high |
| S1 CLI runner | `stage-1-cli.md` | S0 | direct | inline | sonnet | low |
| S2 Status page | `stage-2-status-page.md` | S0, S1 | direct | inline | sonnet | med |
| SF Plan review | `stage-f-review.md` | S2 | direct | inline | sonnet | med |

This table is the **single authoritative home** for every stage's `depends` /
`mode` / `exec` / `model` / `effort`. Stage files never restate them (a copy is
what drifts), and the tooling reads them from here: `/plan-run`'s weight check
reads `model`/`effort` from this index, and the next-runnable-stage logic reads
`depends` from it. A stage that isn't in this table is invisible to both — so
adding a new stage (including one the final review spawns) means adding its row
here first.

Flag values: `mode` = `direct` \| `brainstorm`; `exec` = `inline` \|
`subagent(<model>)`; `model`/`effort` = launch hints (checked, not faked).
Defaults are deliberately cheap — `direct`, `inline`, the cheaper capable
model. Escalate only where a stage has genuine open design questions
(`brainstorm`) or heavy iteration churn (`subagent`).

## Operating protocol (every stage session)

0. **Preflight & sync (required):** run this before reading any status or
   touching any branch. The ledger is canonical but may only be trusted
   *after* it passes — git state inherited from a previous session, a remote
   merge, or a crash is verified here, never assumed.
   1. **Fetch:** `git fetch origin`.
   2. **Sync the plan branch:** fast-forward local `plan-uptime-page` to
      `origin/plan-uptime-page` — `git merge --ff-only origin/plan-uptime-page`
      when it is checked out, `git fetch origin plan-uptime-page:plan-uptime-page`
      otherwise (both refuse non-fast-forward updates). This holds under both
      remote squash-merge and merge-commit: either way the remote plan branch
      only moves forward. If it won't fast-forward, the branch has diverged —
      stop and report.
   3. **Verify the tree:** clean working tree required. If dirty, stop and
      list exactly what is uncommitted — never auto-stash.
   4. **Verify position:** HEAD must be on the plan branch (fresh stage) or
      on the stage branch being resumed. Detached HEAD or any other branch →
      stop and report.
   5. **Reconcile ledger vs reality:** cross-check the `LEDGER.md` status
      table against actual branch and PR state (`gh pr list --base
      plan-uptime-page --state all`, `git branch -a --no-merged
      plan-uptime-page`). One mismatch is self-healing: a `doing` row whose
      stage PR is already merged means the merge happened remotely — complete
      the finish protocol's post-merge bookkeeping (finish step 5) by
      recording the row `done` on the plan branch. Every other mismatch is
      drift — report each one and stop: a `done` row with an open or unmerged
      stage PR; a `todo` row with an existing stage branch that has commits
      (crashed session); an open stage PR based on `main` instead of
      `plan-uptime-page`.
   6. **Report, don't repair:** on anything preflight can't fast-forward or
      reconcile, stop with an accurate report of the state and what would fix
      it — no auto-stash, no reset, no branch deletion.
1. **Read only:** this file + the target stage file + the `LEDGER.md` status
   table + the notes blocks of the stages this one `depends` on + any docs the
   stage file names. Do NOT scan the rest of the repo. (Exception: the final
   review stage reads the *entire* ledger.)
2. **Weight check:** compare the session's model against the stage's `model`
   flag (your system prompt states your model), checked mechanically against
   the `staged-rollout` skill's **Model weight tiers** rubric — not a guess
   about your own weight; remind the recommended `effort` — effort is NOT
   introspectable, so never claim to verify it. If the session is lighter than
   recommended, say so and offer continue/abort before doing anything. If the
   disclosed model doesn't recognizably match a tier in the rubric, don't
   guess — state the exact model ID/name and ask the user which tier applies.
3. **Dependency gate:** for every `depends` stage, confirm it is `done` in
   `LEDGER.md` **AND its stage branch/PR is merged into the plan branch**
   (`git fetch` first — the merge may be remote and not yet local). Both must
   hold. A `done` ledger row alone is not enough: a stage branched off the
   plan branch before a prerequisite's PR is merged will silently lack that
   prerequisite's work. If either isn't true, stop and say so.
4. **Branch:** create `plan-uptime-page-s<N>` from `plan-uptime-page` —
   preflight step 2 already brought it up to date (or use the stage branch if
   the human already made it). Work happens on the stage branch. **Redo:**
   re-running a `done` stage cuts a fresh `plan-uptime-page-s<N>-redo-<K>`
   branch from the current plan branch tip — never reuse a merged stage
   branch.
5. **Honor `mode` / `exec`:**
   - `mode: direct` → state a one-line plan, then implement.
   - `mode: brainstorm` → run a design pass scoped to THIS stage first,
     treating frozen decisions as settled; land outcomes as frozen decisions
     here, not in a second spec.
   - `exec: inline` → implement in this session.
   - `exec: subagent(<model>)` → act as orchestrator and dispatch the
     implementation to a subagent so the churn stays out of this context.
6. **Scope discipline:** do only this stage. Work belonging to another stage →
   note it in the ledger notes and leave it untouched. It may become a new
   stage.
7. **Finish protocol (required):**
   1. Run the stage's **Acceptance** checks; paste the real output into the
      stage's notes block in `LEDGER.md`.
   2. Update the stage's table row: absolute date, verified yes/no, one-line
      result — but the status stays `doing` here. `done` is recorded only
      after the PR merges (step 5 below), so a `done` row is always visible
      from a synced plan branch. Detail goes in the notes block, never the
      table.
   3. If a decision changed or was added, amend **Frozen decisions in this
      file** — nowhere else.
   4. Commit on the stage branch throughout the stage at logical units
      (conventional messages) — not one commit at the end. Push the branch
      and **open the PR** into `plan-uptime-page` (compulsory, not offered),
      pinning the base explicitly — `gh pr create --base plan-uptime-page` —
      never relying on the default, which falls back to the repo's default
      branch (`main`). Then **offer** to merge it once reviewed — never merge
      on your own. Stage PRs are **squash-merged** (one commit per stage on
      the plan branch), and the merged stage branch is deleted. The stage
      cannot be marked `done` until this PR is merged.
   5. **After the merge:** check out `plan-uptime-page` and fast-forward it
      (`git fetch origin` + `git merge --ff-only origin/plan-uptime-page`),
      then flip the stage's row to `done` as a direct commit on the plan
      branch and push. The `done` edit lives on the plan branch, after the
      merge — never on the stage branch. If the merge doesn't happen this
      session, leave the row `doing` and end anyway; the next session's
      preflight (step 0.5) completes this bookkeeping when it finds the
      merged PR. End the session with HEAD on the plan branch.
   6. Announce: this stage is **finished**; the next runnable stage (the first
      `todo` whose `depends` are all `done`), the exact prompt/command to run
      it, and its recommended model/effort. Then stop.
