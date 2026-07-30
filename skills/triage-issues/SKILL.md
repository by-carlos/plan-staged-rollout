---
name: triage-issues
description: Triage GitHub issues across one or more repos and rank them into a Projects (v2) board queue — dedup/consolidate, fix hygiene, and set Status/Priority/Size/Effort so `/work-issue next` can burn the queue down. Runs incrementally by default (deep-reads only untriaged issues); pass `--full` for an exhaustive sweep. Use for backlog triage, deduplication, or board grooming.
---

Run a reproducible GitHub issue triage session. The output is a **ranked queue on a
GitHub Projects (v2) board** — not a local file — that `/work-issue next` consumes.
Same stages, same format, every run. Skimmable, no filler.

## Board schema (the contract with `/work-issue`)

The board is the source of truth. Triage writes these fields; `/work-issue next`
reads them. Reading and writing project fields needs the `project` scope on `gh`
(`gh auth refresh -s project`).

| Field | Type | Meaning |
|-------|------|---------|
| **Status** | single-select | `Ready` = a Claude Code session can pick it up **now**. Anything not `Ready` (`Backlog`, `In progress`, `In review`, `Done`) is excluded from the queue. |
| **Priority** | single-select `P0`–`P3` | primary sort key |
| **Size** | single-select `XS`–`XL` | secondary sort key (smaller first) |
| **Effort** | single-select | model + reasoning-effort recommendation: `haiku`; `sonnet-{low,med,high,extra,max,ultracode}`; `opus-{low,med,high,extra,max,ultracode}`; or `human` (needs physical/account/GUI access Claude Code can't do) |

**Readiness invariant — set `Status = Ready` only when all hold:**
- Priority, Size, and Effort are all set, **and**
- Effort ≠ `human` (human-only work stays `Backlog` so `next` never grabs it), **and**
- the issue is dispatch-ready (clear repro/constraints/verify — not a stub).

Anything failing these stays `Backlog`. Enable the board's built-in **"Item closed →
Done"** workflow once, so a merged `Closes #n` auto-completes the card — triage never
has to un-queue finished work.

**Queue order** among `Ready` items: `(Priority P0<P1<P2<P3, then Size XS<…<XL, then
issue number asc)`.

<role>
You are running a GitHub issue triage session. Output must be reproducible across runs:
same stages, same format, skimmable, no filler.
</role>

<scope>
- **Repos:** the repos named at invocation (e.g. `by-carlos/linux by-carlos/openwrt`).
  If none are named, default to the current repo.
- **Board:** the Projects v2 board named at invocation (URL or number + owner). If none
  is named, default to the board the in-scope issues already sit on. A single board may
  hold items from several repos — that is expected and fine.
- **Project eligibility:** an issue is eligible when it is already on the target board
  **or** has no `projectItems` at all. A target-board item stays eligible even when it
  also appears on another Project. An issue is **externally assigned** only when it is
  absent from the target board and has an item on another Project: report it as excluded,
  do not deep-read it, and never add or edit its target-board item. (Issues belong to
  repositories; this rule concerns GitHub Projects, not repository ownership.)
- **Mode:** default runs are **incremental** — only *unsettled* issues get the
  expensive per-issue deep read (Stage 0). Passing `--full` at invocation restores
  the exhaustive behavior: every eligible scoped open issue is deep-read and deduped against
  the scoped open queue. Use `--full` when the open queue may have drifted or a
  fresh dedup is wanted. Historical `Done` cards are not queue work; inspect them
  only when an explicit history audit is requested.

An issue is **settled** (skipped in incremental mode) when its board fields already
exclude it from future queue work: `Status = Ready`, **or** `Effort = human`.
Everything else — not on the board, empty Status, empty Effort, `Backlog`,
`In progress`, `In review` — is **unsettled** and gets the full deep read.
</scope>

<process>
Stage 0 — Gather
- **Scoped open-issue snapshot (always, exactly once).** List every open issue in
  each scoped repo with `gh issue list` (numbers, titles, labels), saving the raw
  response. Check `gh api rate_limit --jq '.resources.graphql'` before fetching
  Project fields. Retrieve each open issue's `projectItems` and single-select
  `fieldValues`, preferably in one paginated GraphQL query; exact per-issue GraphQL
  reads are acceptable when the scoped set is small. Retain every Project identity first
  to classify eligibility; for eligible issues, select only the target Project locally
  and save the raw field response before parsing. `gh issue view --json
  projectItems` exposes only Status, so use GraphQL when Priority, Size, or Effort
  are required. Do **not** call `gh project item-list` during ordinary triage: it
  retrieves completed history and its cost grows with every closed card.
- **Historical audit (explicit only).** If the user explicitly asks to inspect
  historical board hygiene, first query the Project item `totalCount`, then take one
  `gh project item-list` snapshot with an exact sufficient bound and save it. Never
  use this audit path merely to triage the current queue.
- **Classify.** Identify target-board items first. Exclude an issue only when it lacks a
  target-board item and has another Project item, recording the issue number and Project
  name/URL. An issue with no Project items is eligible to add to the target board. Using
  the matching target-Project fields for eligible issues, split them into **settled**
  (`Status = Ready`, or `Effort = human`) and **unsettled** (everything else). In
  `--full` mode, treat every eligible open issue as unsettled.
- **Deep pass (unsettled only, unless `--full`).** For each unsettled issue, pull the
  full body, comments, and cross-references (`gh issue view <n> --comments`).
  **Resolve every cross-reference, and check whether the work already shipped.** For each
  `#N` an issue names (umbrella, parent, "part of", "supersedes", "duplicate of"), pull
  that issue's state. If it is closed, get *what closed it* —
  `gh issue view <N> --json state,stateReason,closedByPullRequestsReferences` (the closing
  PR lives in `closedByPullRequestsReferences`; it is **not** in `comments`, and an empty
  comments array is not "no explanation"). Then read that PR's body and changed files
  (`gh pr view <p> --json body,files`). A closed-as-`COMPLETED` parent whose PR touches
  the open issue's affected files is a strong signal the fix already merged and the child
  was merely never closed — carry it to Stage 2 §0, do not assume the parent was closed by
  mistake.
- **Settled issues are carried forward on their existing board fields — no deep read,
  no re-examination.** Their Status/Priority/Size/Effort stay as-is.
- Check repo layout only as needed to sanity-check "affected files" claims.
- If `jq` is unavailable, use another parser (e.g. `python -c`) — don't stall on tooling.
- If an issue references images/screenshots you can't render, say so on that issue's line.
  Never guess at unseen content.

Stage 1 — Board & metadata hygiene
Hygiene runs over **all eligible scoped open issues and their matching board items** using
the cheap pass — no deep read needed, so incremental mode never hides a mis-set field.
Externally assigned issues are reported as excluded only. Only the Stage 2 body-level
analysis is scoped to unsettled issues. Completed board history is excluded unless the
user explicitly requested a historical audit.
- Flag open issues missing from the board.
- Flag `Ready` items that violate the readiness invariant (missing Priority/Size/Effort,
  or Effort = `human`).
- Flag issues with thin or missing labels.
- Flag priority drift: issue body states one priority, board field says another.
- Flag closed-parent / open-child anomalies: any open issue citing an umbrella or parent
  that is already closed-as-`COMPLETED` — its fix may already be merged. Resolve in Stage 2 §0.
Findings only — no writes yet.

Stage 2 — Consolidate & analyze
Output ONE numbered, skimmable list, grouped under these headers, one line per item:
0. **Already resolved (check first).** Open issues whose described fix is already merged —
   the umbrella/parent they cite was closed by a merged PR that covers their scope, or their
   named affected files already carry the change. Verify against the current tree (read the
   PR diff, or `git log --oneline -- <affected files>` since the issue was filed), then close
   as completed-by-#N — never queue, consolidate, or re-implement. Pull these out before all
   downstream logic, same as Broken. A closed-`COMPLETED` parent is evidence the fix shipped,
   not that it was closed in error — prove it against the tree before concluding either way.
1. **Duplicates** — issues that are the same work; which closes into which survivor.
   In incremental mode, dedup runs **among the unsettled batch only** (those are already
   deep-read, so it is free). Comparing unsettled issues against settled (`Ready` /
   `human`) items happens **only under `--full`**, since that forces deep reads of
   settled items.
2. **Consolidate** — distinct issues whose scope overlaps enough that working them
   separately would conflict or re-tread the same files. Merge them into ONE issue:
   name the survivor, rewrite its body to cover the combined scope, bump its Size/Effort
   to match, and close the rest as superseded. Do **not** consolidate loosely-related
   issues — leave those separate; the queue order already places them adjacently.
3. **Gaps** — issues too thin to dispatch (no repro/constraints/verify). Name them;
   these stay `Backlog`, not `Ready`.
4. **Broken/nonsensical** — issues that don't hold up (self-contradictory, reference
   removed code, unfalsifiable). Flag for separate handling — keep them out of the
   dedup/ranking logic.
5. Hygiene items carried from Stage 1.
End Stage 2 with a single go/no-go request covering every proposed write (closures, body
rewrites, consolidations, label/field fixes). Wait for it. Don't ask per-item.

Stage 3 — Apply (only after go-ahead)
- Execute exactly what was approved.
- **Closures/consolidations:** close as duplicate/superseded, comment linking the survivor.
- **Body rewrites:** match the repo's existing issue-body template if one exists;
  otherwise Problem / Proposed fix / Affected files. Apply directly if the repo already
  has template precedent; show the draft first only if it doesn't.
- **Board writes:** set Priority, Size, and Effort on each surviving issue, then flip the
  dispatch-ready ones to `Status = Ready` (honoring the readiness invariant). Use
  `gh project item-edit --id <item-id> --project-id <pid> --field-id <fid> --single-select-option-id <oid>`
  (resolve field/option IDs from `gh project field-list <n> --owner <owner> --format json`).
  Everything not dispatch-ready stays `Backlog`.
- One-line summary of what was applied, no more.

Stage 4 — Rank & report
The board is now the queue. Print ONE markdown table as a **read-only snapshot** of what
you just wrote (it is not the source of truth — the board is), priority first then
smaller-size first:

| # | Issue | Repo | Status | Pri | Size | Effort |

- `Effort` = the value you wrote. For non-`Ready` rows, note why in the Effort cell
  (`human`, `needs refinement`, `broken`).
- No batching / no ⏸ rows — every dispatchable item is a single self-contained issue.
</process>

<output_format>
- Stage 2: numbered list only — no prose paragraphs, no restating issue bodies.
- Stage 4: one table, no restating Stage 2.
- Nothing outside these two structures except the Stage 2→3 go/no-go line and the
  one-line post-apply summary.
</output_format>

<rules>
- Never batch-close, batch-edit, or write board fields without the Stage 2→3 go-ahead.
- Never add to, remove from, or edit the target-board item of an externally assigned issue.
- Never guess at unreadable content — state the limitation.
- `Ready` is the only readiness signal; there is no separate readiness section.
- Default runs are incremental: deep-read only unsettled issues (`Status ≠ Ready` **and**
  `Effort ≠ human`). Never deep-read or re-dedup settled issues unless `--full` is passed.
- Consolidate overlaps into one issue — never leave a "work these together" batch for the
  queue consumer to reconcile.
- Never queue or re-implement work that already merged. When an issue cites a closed
  umbrella/parent, read its closing PR (`closedByPullRequestsReferences`) before theorizing
  why the issue is still open — a closed-`COMPLETED` parent usually means the fix shipped and
  the child was never closed, not that it was closed by mistake.
</rules>
