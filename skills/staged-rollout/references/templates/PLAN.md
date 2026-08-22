# <Project name> — plan & protocol

<One-paragraph statement of what this project builds and why. If a longer
design narrative exists, point at it here and keep this file as the executable
spec.> This file is the **single source of truth** for durable decisions: the
architecture, the frozen decisions, the stage index, and the operating
protocol every stage session follows. Decisions live here and are *referenced,
never copied* — a decision that exists in one place cannot diverge.

## Architecture (what we're building)

```
<Sketch the target layout / components here — the shape the finished work
takes. Keep it current; amend it when a stage changes the design.>
```

## Frozen decisions

Change these in THIS file only — never restate them in stage files or the
ledger. If a stage changes a decision, amend it here as the last step of that
stage (Operating protocol, finish step 3).

- <Decision 1 — e.g. naming, key library/tool choice, a hard constraint.>
- <Decision 2.>
- **Git strategy:** branch-per-stage (fixed — the only supported model).
  `.plan/` is **tracked** on the plan branch and the plan branch has an
  **upstream** — both are load-bearing, not housekeeping (preflight step 0.0).
  `main` → `plan-<slug>` (the plan branch; `.plan/` lives here) → one branch
  per stage `plan-<slug>-s<N>` (flat names — git refs can't nest a branch
  under an existing branch), each landing as a **squash-merged** PR into
  `plan-<slug>`; final PR `plan-<slug>` → `main` at closeout is a **normal
  (non-squash) merge** so each stage keeps its own commit on `main`. Commits on
  a stage branch are compulsory
  and incremental (logical units as the stage progresses, not one commit at
  the end). The agent creates and pushes stage and plan branches without
  asking, and **opens** the stage PR as a compulsory part of finishing a
  stage — never merging without your OK, never pushing to `main`. The one
  carve-out is the plan-level `merge: auto` flag (Stage index, plan flags
  line): it gives that OK in advance for **stage PRs only**, so the session
  squash-merges its own stage PR once checks are green; the plan→main PR is
  manual in every mode. A stage
  cannot be marked `done` until its PR is merged into the plan branch; the
  `done` edit itself is committed on the plan branch *after* the merge
  (Operating protocol, finish step 5), never on the stage branch.
- **Worktree strategy:** worktree-per-stage (fixed — the only supported
  model). *The clone holds the plan; worktrees hold the work.* The main clone
  stays parked on `plan-<slug>` for the life of the plan — that is the only
  branch ever checked out there, which is what keeps `.plan/` readable and the
  `done` write committable at any moment without disturbing an in-flight
  stage. Each stage branch is checked out **only** in its own sibling
  worktree, `../<repo-dirname>-s<N>` (`-redo-<K>` for a redo), created from
  the plan branch tip. Provisioning prefers the harness's native worktree
  mechanism, but only when it honors this convention's exact branch and path
  names, and falls back to `git worktree add` otherwise; it never degrades
  to checking a stage branch out in the clone (Operating protocol, step 4).
  Teardown is part of finishing: a clean, fully-pushed worktree is removed
  with its merged branch, and anything else is left alone and reported
  (finish step 5).
- **Final review stage:** the last stage (`SF`) is a standing plan review. It
  catalogs loose ends — each becomes a new in-plan stage, a spin-off
  candidate, or an explicit "accepted, won't fix" — and NEVER implements.

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort | gate |
|---|---|---|---|---|---|---|---|
| S0 <keystone stage — the piece everything needs> | `stage-0-<slug>.md` | — | direct | inline | <model> | <effort> | auto |
| S1 <stage name> | `stage-1-<slug>.md` | S0 | direct | inline | <model> | <effort> | auto |
| ... | ... | ... | ... | ... | ... | ... | ... |
| SF Plan review | `stage-f-review.md` | <last impl stage> | direct | inline | <model> | <effort> | auto |

Plan flags: `merge: manual` · `plan-dir: delete`

This table is the **single authoritative home** for every stage's `depends` /
`mode` / `exec` / `model` / `effort` / `gate`, and the **plan flags** line
under it is the home of the plan-level `merge` and `plan-dir` flags. Stage
files never restate them (a copy is what drifts), and the tooling reads them
from here: `/plan-run`'s weight check reads `model`/`effort` from this index,
the runnable-set logic (below) reads `depends` from it, an unattended runner
reads `gate` and `merge`, and `/plan-close` reads `plan-dir`. A stage that
isn't in this table is invisible to all of them — so adding a new stage
(including one the final review spawns) means adding its row here first.

The two plan flags are this plan's **declared defaults**: the answers a
session applies when there is nobody to ask (`--unattended`). An interactive
session still asks, taking the declared value as its recommendation. See the
`staged-rollout` skill, *Unattended mode*, for the full classification of
which questions have a default and which are hard stops in every mode.

Flag values: `mode` = `direct` \| `brainstorm`; `exec` = `inline` \|
`subagent(<model>)`; `model`/`effort` = launch hints (checked, not faked);
`gate` = `auto` \| `human` (may the stage be launched with nobody watching? —
`human` means never); `merge` = `manual` \| `auto` (does the session merge its
own stage PR into the plan branch once checks are green, or offer it for your
OK?); `plan-dir` = `delete` \| `keep` (at closeout, is `.plan/` removed as the
last commit on the plan branch, or left in place because the plan doubles as
documentation?). Defaults are deliberately cheap and preserve the fully-manual
flow — `direct`, `inline`, the cheaper capable model, `gate: auto`,
`merge: manual`, `plan-dir: delete`; a missing `gate` column, a missing
plan-flags line, or a missing entry on it means those defaults. Escalate only
where a stage has genuine open design questions (`brainstorm`, which also
makes it `gate: human`) or heavy iteration churn (`subagent`). `merge` governs
stage PRs only — the plan→main PR at closeout is manual in every mode.

### Runnable set & waves (derived, never stored)

The `Depends` column is a full dependency graph, so everything about execution
order is **derived from it** — waves and parallelism are never written down as
their own column. A stored copy is what drifts; the graph is the truth.

- **Runnable set:** every stage whose `LEDGER.md` status is `todo` and whose
  `depends` are all `done`, plus any `doing` stage (resumable). This is a
  *set*, not a single stage. When it holds more than one, those stages have no
  dependency on each other and can be run **concurrently, one per fresh
  session**.
- **Waves:** wave 0 is every stage with no `depends`; wave *k* is every stage
  whose deepest prerequisite sits in wave *k−1*. The number of waves is the
  fewest rounds the plan can take, and the **critical path** — the longest
  chain of `depends` edges — is the floor on elapsed time that no amount of
  parallelism removes.
- **`depends` means "cannot safely start until", not "written after".** List
  only genuine prerequisites. Chaining `S0 → S1 → S2 → S3` when the real graph
  is `S0 → {S1, S2, S3}` costs three rounds instead of two and hides the cost,
  because the index still looks correct.
- **Concurrency is an operator action.** Nothing here launches sessions:
  running a wave in parallel means opening one session per stage yourself —
  or leaving it to an unattended runner outside any session, which launches
  only `gate: auto` stages and stops in front of a `gate: human` one. What
  the protocol owes you is that doing so is safe — see *Concurrent stages*
  below.

### Concurrent stages (when the set fans out)

Running two stages at once changes nothing about the git model: still one
branch per stage, one PR per branch, one stage per session. It adds one
structural fact and four rules about timing.

- **Separate working trees are what make concurrency physical.** Each stage
  runs in its own worktree, so two sessions never contend for `HEAD` and
  neither can see the other's uncommitted work. The rules below are about
  what happens when their *branches* meet at the plan branch.
- **A sibling's stage branch is expected state, not drift.** Two stage
  branches cut from the same plan-branch tip is exactly what a fan-out looks
  like. Preflight step 0.5 classifies by whose stage the mismatch belongs to:
  drift on the stage *this* session is about to run still stops it, while
  another stage's in-flight branch is reported and stepped over.
- **The plan branch is the serialization point.** Parallel stage PRs merge
  **one at a time, first come first served** — there is no queue to manage.
  Whoever merges second re-syncs first (finish step 4): merge the plan branch
  *into* the stage branch, resolve there, and re-run the acceptance checks. A
  PR GitHub calls "mergeable" only means no textual conflict — not that this
  stage still passes after the sibling's change landed.
- **Shared write territory is a `depends` edge.** Two stages with no logical
  relationship can still write the same files, and `Depends` is the only place
  that can express it — so express it there and let the wave structure narrow
  accordingly. There is deliberately **no** separate "territory" field: a
  second place to record the same constraint is a second thing to drift. If
  the overlap is small and genuinely order-independent, leaving both stages in
  one wave is a legitimate choice, and the re-sync-and-re-verify rule above is
  the net that catches it.
- **The `done` ledger write can race.** It is a direct commit on the plan
  branch (finish step 5), so two sessions finishing minutes apart collide
  there. Finish step 5 says how: edit after the fast-forward, replay on
  rejection, never force-push the plan branch.

## Operating protocol (every stage session)

0. **Preflight & sync (required):** run this before reading any status or
   touching any branch. The ledger is canonical but may only be trusted
   *after* it passes — git state inherited from a previous session, a remote
   merge, or a crash is verified here, never assumed.
   0. **Verify the plan is real git, not a loose directory.** Two checks,
      both hard gates — the whole protocol rests on them:
      - **`.plan/` is tracked:** `git ls-files --error-unmatch .plan/PLAN.md`.
        If it fails, `.plan/` is untracked or ignored — stop. An untracked
        plan produces no committable content, so stages that only amend
        `PLAN.md`/`LEDGER.md` can never open a PR, which makes every
        downstream dependency gate unsatisfiable; and the entire decision
        record dies with the working directory. Fix by removing the ignore
        rule (`git check-ignore -v .plan/PLAN.md` names it) and committing
        `.plan/` on the plan branch before running any stage.
      - **The plan branch has an upstream:**
        `git rev-parse --abbrev-ref plan-<slug>@{upstream}`. If it fails, the
        branch is local-only — the fetch and fast-forward below would succeed
        while doing nothing, forever. Push it (`git push -u origin
        plan-<slug>`) and continue; pushing a feature branch needs no
        approval.
   1. **Fetch:** `git fetch origin`.
   2. **Sync the plan branch:** fast-forward local `plan-<slug>` to
      `origin/plan-<slug>` — `git merge --ff-only origin/plan-<slug>` when it
      is checked out, `git fetch origin plan-<slug>:plan-<slug>` otherwise
      (both refuse non-fast-forward updates). This holds under both remote
      squash-merge and merge-commit: either way the remote plan branch only
      moves forward. If it won't fast-forward, the branch has diverged — stop
      and report.
   3. **Verify the trees:** a clean working tree is required in *this* tree
      **and** in the main clone. The clone matters even when the stage runs
      elsewhere: the `done` write (finish step 5) is a commit there, so a
      dirty clone blocks the stage from ever closing. If either is dirty,
      stop and list exactly what is uncommitted — never auto-stash.
   4. **Verify position (the two-tree rule):** the clone is parked on
      `plan-<slug>`; stage branches live only in sibling worktrees. Establish
      which tree this session is in — inside a worktree `git rev-parse
      --git-dir` and `--git-common-dir` differ; in the clone they match —
      then check:
      - **The clone's HEAD must be `plan-<slug>`.** A stage branch checked
        out there is drift: stop and report. The fix is to check the plan
        branch back out in the clone and give that stage its own worktree —
        never run the stage in the clone.
      - **A fresh stage starts in the clone**, which is where step 4 creates
        its worktree.
      - **A resumed stage must run inside that stage's worktree.** If the
        worktree exists but this session is in the clone, print its path and
        enter it (step 4's provisioning rule) — do not check the branch out.
      - Detached HEAD anywhere, or a worktree whose HEAD is not its own stage
        branch → stop and report.
   5. **Reconcile ledger vs reality:** cross-check the `LEDGER.md` status
      table against actual branch and PR state (`gh pr list --base
      plan-<slug> --state all`, `git branch -a --no-merged plan-<slug>`).
      Classify each mismatch by *whose* stage it belongs to — the stage this
      session is about to run, or another one:
      - **Self-healing:** a `doing` row whose stage PR is already merged
        means the merge happened remotely — complete the finish protocol's
        post-merge bookkeeping (finish step 5) by recording that row `done`
        on the plan branch.
      - **Drift — report and stop:** a `done` row with an open or unmerged
        stage PR; an open stage PR based on `main` instead of
        `plan-<slug>`; and **this session's own stage** showing a `todo` row
        while its stage branch already exists with commits (a crashed
        earlier attempt at the very stage you are starting — resume it or
        discard it, don't run over it).
      - **Report and continue:** *another* stage's `todo` row with an
        existing stage branch that has commits. Under concurrent execution
        that is the ordinary signature of a **live sibling** — a session
        working that stage right now, whose `doing` flip and evidence are
        still on its own unmerged branch and therefore invisible from here.
        Halting would stop every parallel session, so list each one in the
        preflight report (stage id, branch, whether it has an open PR) and
        carry on. Detection is re-aimed, not weakened: the same signature
        with no session behind it is a crashed stage, it reappears in every
        later preflight report, the final review stage sees it, and closeout
        still refuses to run while any stage PR is open or unmerged.

      Then reconcile **worktrees** by the same rule, from `git worktree list
      --porcelain` — but only worktrees whose branch matches
      `plan-<slug>-s*`. An operator's unrelated worktree (any other branch)
      is none of this plan's business: it is ignored entirely, never
      classified into any bucket below and never offered for removal. A
      worktree belonging to *this* session's stage that this session did not
      create is the crashed-attempt case — stop, resume or discard it, don't
      run over it. A worktree for *another* `todo`/`doing` stage is the
      ordinary live sibling — list it and carry on. A worktree whose stage
      branch is already merged or gone is an **orphan** from an interrupted
      teardown — report its path and offer removal; never remove it unasked,
      and never assume it is empty.
   6. **Report, don't repair:** on anything preflight can't fast-forward or
      reconcile, stop with an accurate report of the state and what would fix
      it — no auto-stash, no reset, no branch deletion, no `git worktree
      remove --force`, and no automatic `git worktree prune`.
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
   **Unattended?** If this session was launched with nobody to answer it (an
   unattended runner, or `/plan-run`'s `--unattended` argument), check the
   stage's `gate` first: a `gate: human` stage is never started unattended —
   report that and stop here. For a `gate: auto` stage, every offer or
   question in this step and the ones below either has a **declared default**
   on the plan flags line or is a **hard stop** — there is no third option
   and nothing waits for an answer (see the `staged-rollout` skill,
   *Unattended mode*, for the full classification). Nothing in this step has a
   declared default, so a lighter-than-recommended model or an unrecognised
   tier marks the row `blocked` with the mismatch as the runbook, commits,
   and stops.
3. **Dependency gate:** for every `depends` stage, confirm it is `done` in
   `LEDGER.md` **AND its stage branch/PR is merged into the plan branch**
   (`git fetch` first — the merge may be remote and not yet local). Both must
   hold. A `done` ledger row alone is not enough: a stage branched off the
   plan branch before a prerequisite's PR is merged will silently lack that
   prerequisite's work. If either isn't true, stop and say so. This gate is
   always satisfiable: **every** stage has repo artifacts, because `.plan/` is
   tracked and every stage edits the ledger — a documentation- or
   decision-only stage still commits its `PLAN.md`/`LEDGER.md` changes and
   still opens a PR. A depends-stage with no PR means preflight step 0.0 was
   skipped, not that the stage was exempt.
4. **Branch & worktree:** the stage runs in its own sibling worktree and the
   clone stays on the plan branch (frozen decision above). Create branch and
   worktree together from the plan branch, which preflight step 2 already
   brought up to date — or use them as-is if the human already made them:
   - **Prefer the harness's native mechanism** where there is one (Claude
     Code's `EnterWorktree`, or the `superpowers:using-git-worktrees` skill
     when installed) — but only if it honors this protocol's naming
     convention (branch `plan-<slug>-s<N>`, path `../<repo-dirname>-s<N>`).
     A mechanism that picks its own path or branch name breaks the ledger's
     path references, the teardown command, and the next session's resume
     lookup — none of them can find a worktree under any name but this one.
     If it can't be pointed at this exact name and path, don't use it.
   - **Otherwise:** `git worktree add ../<repo-dirname>-s<N> -b
     plan-<slug>-s<N> plan-<slug>`, then work there by absolute path for the
     rest of the stage.
   - **If the harness refuses to work outside its starting directory:** stop,
     print the worktree path, and tell the operator to relaunch this stage
     with that path as the working directory. **Never** fall back to checking
     the stage branch out in the clone — that closes the ledger window and
     breaks every concurrent session.
   - **A fresh worktree holds only tracked files.** Untracked local setup the
     stage needs — `.env`, local config, build caches, dependency directories
     — is not there. Copy what it needs and record in the ledger notes what
     you copied, because the next session starts from the same blank slate.
   **Redo:** re-running a `done` stage cuts a fresh
   `plan-<slug>-s<N>-redo-<K>` branch in its **own** worktree
   (`../<repo-dirname>-s<N>-redo-<K>`) from the current plan branch tip —
   never reuse a merged stage branch or its worktree.
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
      (conventional messages) — not one commit at the end. Everything in this
      step — commits, push, the PR, any sibling re-sync merge — happens
      **inside the stage worktree**, never in the clone. There is no such
      thing as a stage with nothing to commit: steps 1–3 above always change
      tracked files under `.plan/`, so a stage whose Artifacts are "no host or
      secret changes" still lands its ledger evidence and any frozen-decision
      amendment as a commit. Push the branch
      and **open the PR** into `plan-<slug>` (compulsory, not offered),
      pinning the base explicitly — `gh pr create --base plan-<slug>` — never
      relying on the default, which falls back to the repo's default branch
      (`main`). Then **offer** to merge it once reviewed — never merge on
      your own. Stage PRs are **squash-merged** (one commit per stage on the
      plan branch), and the merged stage branch is deleted. The stage cannot
      be marked `done` until this PR is merged.
      **Under `merge: auto`** (plan flags line): the OK is given in advance
      for stage PRs, so once the sibling re-sync check below has run and
      every required check on the PR is green, squash-merge it yourself
      (`gh pr merge --squash --delete-branch`) and continue straight to step
      5. Never force or retry past a refusal — a red or missing check, or a
      protection rule on the plan branch, means the merge did not happen this
      session: leave the row `doing`, report the refusal and why, and end;
      the next preflight (step 0.5) finishes the bookkeeping once someone
      merges it. `merge` never applies to the plan→main PR.
      **Merge order with a sibling in flight:** parallel stage PRs merge one
      at a time, first come first served — the plan branch is the
      serialization point, so there is no queue to coordinate. Before
      offering the merge, `git fetch origin` and check whether
      `origin/plan-<slug>` has moved past this stage branch's merge base. If
      it has, a sibling merged while this stage was in flight: merge the plan
      branch *into* the stage branch (`git merge origin/plan-<slug>`),
      resolve any conflict there, push, and **re-run the Acceptance checks**,
      replacing the evidence in the ledger notes with the output from the
      merged result. GitHub reporting the PR as mergeable is not enough — it
      means no textual conflict, not that this stage still passes after the
      sibling's change. Never rebase or force-push a stage branch: resolving
      with a merge commit on the stage branch costs the plan branch nothing,
      because the squash merge discards it. If yet another sibling lands in
      the window between the re-sync and the merge, repeat the check — it is
      cheap, and a stale re-verify is worth less than none.
   5. **After the merge:** return to the main clone — it is already on
      `plan-<slug>`, so there is no checkout to do — and fast-forward it
      (`git fetch origin` + `git merge --ff-only origin/plan-<slug>`), then
      flip the stage's row to `done` as a direct commit on the plan branch
      and push. The `done` edit lives on the plan branch, after the merge —
      never on the stage branch. If the merge doesn't happen this session,
      leave the row `doing` and end anyway; the next session's preflight
      (step 0.5) completes this bookkeeping when it finds the merged PR.
      **If a sibling stage is running, this write races.** Both sessions
      commit directly on the plan branch, so: make the edit *after* the
      fast-forward (never before), touch only your own row, and push
      immediately. If the clone is dirty on arrival and the change isn't
      yours — a sibling's session is mid-edit in this same clone — wait and
      retry rather than committing on top of it or folding it into your own
      commit; that is the one case the push-race handling below doesn't cover,
      because it happens before either side has pushed. If the push is
      rejected as non-fast-forward, the sibling won the race by seconds —
      fetch and replay your single ledger commit on top (`git pull --rebase
      origin plan-<slug>`), then push again. **Never
      force-push the plan branch**: last-writer-wins would erase the
      sibling's `done` row. If the replay conflicts, both rows are wanted —
      the two edits touch adjacent lines of the same table, so resolve by
      keeping **both**.

      **Then tear the worktree down, from the clone.** If the stage worktree
      is clean and fully pushed, remove it and delete the merged stage branch:
      `git worktree remove ../<repo-dirname>-s<N>`, then `git branch -D
      plan-<slug>-s<N>`. Use `-D`, not `-d` — the stage PR was squash-merged,
      so git's own merge-tracking never sees this branch as merged into
      `plan-<slug>` and `-d` refuses with "not fully merged" even though the
      squash commit already carries the work safely onto the plan branch,
      which is exactly what makes `-D` safe here. If the worktree holds
      anything uncommitted, unpushed, or stashed, **leave it** and report its
      path and what is in it — a worktree is a real directory and its
      contents are not
      recoverable from git. Never `--force`, never `prune` to tidy up; an
      orphan left behind is reported by every later preflight and gates
      closeout, which is the safe failure. **The two thresholds differ on
      purpose:** a stage leaves anything it is unsure about, and closeout
      sweeps up whichever of those turn out to be merged with nothing
      unpushed. Erring towards leaving costs a line in a report; erring
      towards removing costs a directory git cannot give back. If the merge did not happen this
      session, the worktree stays — teardown belongs with the `done` write.

      End the session in the clone, on the plan branch.
   6. Announce: this stage is **finished**, then the **complete runnable
      set** — *every* `todo` stage whose `depends` are now all `done`, not
      just the first (see *Runnable set & waves* above). For each one, give
      the exact prompt/command to run it, its recommended `model`/`effort`
      and its `gate` from the stage index — a `gate: human` stage needs a
      person at the keyboard, so an unattended runner reading this stops
      there. If the set holds more than one stage, say so
      plainly: they are independent and can be launched **concurrently, one
      per fresh session**. If it is empty, say which it is — every stage
      `done`/`skipped` (ready for closeout) or stalled on `blocked` rows and
      unmet dependencies. Then stop.
