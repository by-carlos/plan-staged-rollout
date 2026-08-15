---
name: work-issue
description: Work a GitHub issue end-to-end — read the thread, gate on scope, branch, implement with conventional commits, open a PR that closes the issue, and squash-merge after explicit confirmation. Use when asked to work, fix, or implement a GitHub issue by number.
---

Work a GitHub issue end-to-end. Two ways to pick the issue:

- **`/work-issue <number> [base]`** — work that specific issue.
- **`/work-issue next`** — pull the top item off the triage queue (the Projects
  board that [`/triage-issues`](../triage-issues/SKILL.md) populates) and work it.

Use the base branch the user names; if none, default to `main`.

## 0. Pick the issue (`next` mode only)

`next` reads the same board schema `/triage-issues` writes, so it needs the `project`
scope on `gh` (`gh auth refresh -s project`).

- Take the queue head — the `Ready` issue with the lowest `(Priority P0<P1<P2<P3,
  then Size XS<…<XL, then issue number asc)`:
  ```
  gh project item-list <number> --owner <owner> --format json --limit 500
  ```
  Filter `status == "Ready"` and `content.type == "Issue"`, sort by those keys, take
  the first. `content.repository` (`owner/repo`) and `content.number` say which repo
  and issue to work; carry `effort` (the recommended model) to the hand-off in §6.
- **Empty queue** → say so and stop.
- On selection, flip the item to `Status = In progress` so a re-run of `next` — or a
  parallel session — won't grab the same issue. Then continue from §1 for that issue.

## 1. Fetch & assess

- **Move to In progress first.** The moment you start investigating, flip the
  issue's board `Status = In progress` — before reading the thread or touching
  anything — so a parallel session won't grab it. In `next` mode this already
  happened at selection (§0); in `/work-issue <number>` mode, do it now if the
  issue is tracked on the triage board (skip silently if it isn't on a board).
- Read the full thread, not just the body — decisions often live in the
  comments: `gh issue view <number> --comments`.
- If the issue embeds images or attachments
  (`https://github.com/user-attachments/...`), fetch them with
  `curl -sL -H "Authorization: token $(gh auth token)" -o <tmpfile> <url>`
  and read them.
- **Scope gate — assess before touching anything:**
  - **Too big** (multi-session epic, several independent deliverables, or
    acceptance criteria too vague to verify): say so, recommend splitting the
    issue or decomposing the work first (e.g. a staged-rollout plan, if that
    plugin is installed), and **stop**. In `next` mode, first set the item's
    `Status = Backlog` and comment on the issue explaining it needs
    splitting/refinement — so the next `next` skips it instead of re-grabbing it.
  - **Too small** (a trivial one-liner where branch/PR ceremony is pure
    overhead): say so and offer to just make the change directly on the
    current branch instead. **Stop and wait** for the choice.
  - Otherwise: state a 1–3 line plan and continue without asking.

## 2. Branch

- `git fetch origin`, then branch off the base:
  `git switch -c <type>/<number>-<slug> origin/<base>`.
- `<type>`: the conventional-commit type matching the issue — `feat`, `fix`,
  `docs`, `refactor`, `test`, or `chore`.
- `<slug>`: 2–5 kebab-case words distilled from the issue title.
- Example: `fix/42-hook-crash-on-empty-plan`.

## 3. Implement & commit

- Do the work following the repo's conventions (CLAUDE.md, existing style,
  existing dependencies).
- Commit each logical unit as you go with conventional commit messages —
  don't batch everything into one commit at the end.
- If the repo keeps a changelog, add the entry as part of the work.

## 4. Pull request

- Push the branch and open the PR against the base:
  `gh pr create --base <base>`.
- PR description: what changed and why, any decisions or trade-offs worth a
  reviewer's attention, and `Closes #<number>` so the merge auto-closes the
  issue.
- **Move to In review.** Once the code is in the PR and every non-merge step is
  done — implementation complete, changelog updated, checks green — flip the
  issue's board `Status = In review` (skip silently if it isn't on a board). The
  issue now sits in review awaiting verification or your go-ahead to merge.

## 5. Merge — always last, confirmation required

- **Merge is the final step, full stop.** Everything else — implementation,
  commits, changelog, PR, any extra work the request bundled in ("do x and
  merge") — must be complete *before* you merge. Never merge with steps
  outstanding: a mid-flight error after merging would auto-close an issue that
  isn't actually resolved. If any bundled task remains, finish it first.
- **Complete user acceptance before presenting the merge gate** when the change
  has a live, visual, interactive, or otherwise user-verifiable acceptance
  surface. Obtain any live-system approval the repository requires, deploy the
  exact PR head through its documented pre-merge test path, run basic health
  checks, give the maintainer the exact location to inspect, and leave that
  deployment available while awaiting explicit acceptance. Automated tests,
  health checks, screenshots, and agent verification support this gate but do
  not replace maintainer acceptance. If the deployment is reverted or
  overwritten before acceptance, redeploy the same PR head before merging. If
  it cannot be deployed safely, report the blocker and do not merge. “Looks
  good, merge it” satisfies both acceptance and merge confirmation when the
  merge risk has already been disclosed.
- Present the PR link and ask for explicit confirmation to merge. **Never
  merge without it.** If confirmation doesn't come, leave the PR open (Status
  stays `In review`) and finish the session cleanly.
- On OK: **squash merge** (unless the repo's own conventions specify a
  different merge type), then tidy up — delete the remote and local branch,
  switch back to the base, and pull.

## 6. Hand off to the next issue (`next` mode only)

- The board's **"Item closed → Done"** workflow moves the merged card to `Done`
  automatically via `Closes #n` — no manual queue edit needed.
- If the merge was **declined**, leave the PR open; the item stays `In review`, so
  `next` won't re-grab it — finish or merge it by hand later.
- Announce the queue head for the next run — one more `gh project item-list` (creds are
  already loaded): **"Next: #NN — \<title\> — suggested model: \<effort\>."** Read
  `effort` straight from the field; never recompute it. If the queue is empty, say so.
