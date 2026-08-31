# Stage-runner contract

The instructions a **cloud session** follows to pick and run exactly one stage
of a `plan-staged-rollout` plan, unattended, with nobody watching once it
starts. It is the cloud-side counterpart of what
[`scripts/plan_driver.py`](../../scripts/plan_driver.py) does locally, and it
is deliberately the *smallest* thing that can run a stage: it works out which
stage is next, follows the plan's own protocol, records what happened where
the plan records it, and stops.

It lives here as a committed file so it can be reviewed and diffed. A fresh
cloud session is pointed at this file rather than carrying its own saved copy
— see [`docs/ON-THE-RUN.md`](../../docs/ON-THE-RUN.md) for exactly what to
type to start one. A change to the contract is a change here first.

> **Status: not yet proven for this transport.**
> [#110](https://github.com/by-carlos/plan-staged-rollout/issues/110) proved
> an earlier design — hand-provisioned cloud *routines*, fired by a
> persistent orchestrator chat session — end to end. That proof predates this
> design and does not carry over to it: nothing here has yet run a real stage
> in a cloud session created this way. This contract is not claimed proven
> until a new proof-of-concept run against
> [`poc/`](poc/) passes.

## Where it runs, and what that changes

A cloud session runs in a fresh, isolated sandbox, with the repository
cloned into it. What follows is true of any cloud session, not particular to
how this one was created:

- **It cannot reach anything outside the sandbox and the repository.** No
  local files on your machine, no local network, no secret that lives only
  on your machine, no locally-installed toolchain. Anything a stage's work
  needs must already be committed to the repository or otherwise reachable
  from the cloud. A stage that needs something local declares `gate: local`
  (or, if it only discovers this mid-run, records a `needs-local` block) —
  see §4, below.
- **No plugin loads inside a cloud session — this one included.** There is no
  `/plan-run` command available. `.plan/PLAN.md` carries the whole operating
  protocol and is designed to work standalone, which is what this contract
  relies on: it tells you to *read and follow* that file, not to invoke a
  command that isn't there.
- **There is no `gh` binary, and no direct GitHub API access.** GitHub reads
  and writes go through an MCP server the platform injects, scoped to the
  one repository this session was pointed at. Two sharp edges: a search or
  list tool that doesn't take a repository argument can reach past that
  scope, and a label write **replaces the entire label list** on whatever
  it's writing to — never assume "add a label" leaves the others alone.
- **A GitHub Projects (v2) board is not reachable from inside this session at
  all.** If a stage's finish protocol would normally update one, that write
  cannot happen here; note it in the ledger instead of attempting it, and
  leave it for a person or a local session.
- **The session acts with its own GitHub identity and no per-action
  approval.** There is no permission-mode picker and nobody to answer a
  prompt. These instructions are the only control on what it does.

## The prompt

Everything between the markers is what the session follows, verbatim.

<!-- BEGIN STAGE-RUNNER PROMPT -->

    You are running exactly one stage of a `plan-staged-rollout` plan, in a
    cloud session. Nobody is watching once you start, and nobody can answer a
    question. These instructions are the only control on what you may do.

    1. CHECK OUT THE PLAN BRANCH BEFORE ANYTHING ELSE.

    You were told a branch name — `plan-<slug>` — when this session started.
    Before reading any status or touching any other branch:

        git fetch origin
        git checkout -B <branch> origin/<branch>

    If `origin/<branch>` does not exist, stop — there is no plan to run.
    Confirm `.plan/PLAN.md` and `.plan/LEDGER.md` are present, then read
    `.plan/PLAN.md` in full.

    2. WORK OUT WHICH STAGE IS NEXT, YOURSELF.

    Nobody is telling you which stage to run — that is your first decision,
    not something handed to you. Apply `.plan/PLAN.md`'s own derived rule: a
    stage is runnable when its `.plan/LEDGER.md` status is `todo` and every
    stage named in its `Depends` column is `done` or `skipped`, or when its
    status is `doing` (a resumable stage, picking up where a previous session
    left off). If more than one stage is runnable, take the lowest-numbered
    one and leave the rest for a later session — do not run more than one
    stage in this session.

    If no stage is runnable and every stage reads `done` or `skipped`, the
    plan's stages are finished. Say so, touch nothing, and stop — closeout and
    the plan-to-`main` merge are not yours; see §7.

    3. FOLLOW `.plan/PLAN.md`'s OPERATING PROTOCOL FOR THE STAGE YOU PICKED.

    That file is the protocol: preflight and sync, read scope, weight check,
    dependency gate, branch and worktree, `mode`/`exec`, scope discipline, the
    finish protocol, and "Recording a block". Follow it as written. This
    contract does not restate it and does not override it, except where a
    rule below says so explicitly.

    No plugin is installed in this session, so there is no `/plan-run`
    command and no plugin skill to invoke. `.plan/PLAN.md` is the only
    protocol you have, and it is complete on its own.

    Treat this session as UNATTENDED everywhere the protocol distinguishes:
    apply the declared defaults on the plan flags line, and take the hard
    stop wherever the protocol says there is no default. Nothing waits for an
    answer, nothing is retried, and nothing is faked past a gate.

    4. REFUSE A `gate: human` OR `gate: local` STAGE, AND RECORD THE REFUSAL.

    Read the stage's `gate` in `.plan/PLAN.md`'s stage index (an absent
    column reads as `auto`). If it is `human` or `local`, do not start the
    stage. Set that stage's row to `blocked` in `.plan/LEDGER.md`, write in
    its notes block that it was picked up by an unattended cloud session and
    needs a person present (`human`) or a machine with local access
    (`local` — write the literal reason `needs-local` in the row's `Result`
    cell), and commit that directly on the plan branch and push — the
    protocol's "Recording a block", before-the-stage-branch-exists case. Then
    stop. Reporting the refusal in your own reply is not enough: nothing
    outside this session can read what you say — only what you push.

    If, partway through a stage that started as `auto`, you discover it
    actually needs something only a local machine has, stop there instead of
    guessing or working around it: record the same `blocked` row with reason
    `needs-local`, following whichever case of "Recording a block" applies —
    before or after the stage branch exists — and stop.

    5. PUSH THE STAGE BRANCH IMMEDIATELY, BEFORE THE WORK.

    As soon as the protocol's branch-and-worktree step has created
    `plan-<slug>-s<N>`, push it — `git push -u origin <stage-branch>` —
    before the bulk of the stage's work, not after. A session that dies
    before pushing is indistinguishable, from outside, from one that never
    started.

    6. THE LEDGER ROW IS THE ONLY COMPLETION SIGNAL.

    Nothing you say in this session's own transcript is a substitute for what
    you push. The only evidence that anything happened is what reaches the
    plan branch: the `done` row committed after the stage PR merges (finish
    step 5), or the `blocked` row and `.plan/BLOCKED.md` section committed
    per "Recording a block". Complete that bookkeeping before you stop,
    including when the stage ends badly. Never substitute a summary, an issue
    comment, a PR comment, or a message for it.

    7. NEVER MERGE INTO THE REPOSITORY'S DEFAULT BRANCH.

    The plan branch to default branch merge is permanently a human step. Do
    not perform it, do not open it, do not report it as done, and never push
    to the default branch or a release branch for any reason.

    Merging THIS stage's own PR into the PLAN branch is a different thing and
    is allowed — exactly when the plan flags line reads `merge: auto` and the
    protocol's conditions hold (sibling re-sync done, every required check
    green). Under `merge: manual`, leave the PR open, leave the row `doing`,
    and stop.

    8. THERE ARE NO PERMISSION PROMPTS IN THIS SESSION.

    You act with your own GitHub identity and no per-action approval. Your
    blast radius is exactly: this clone, the plan branch, this stage's branch
    and worktree, and this stage's pull request into the plan branch. Do not
    touch another repository, another branch, repository or account
    settings, issues, other pull requests, or any GitHub Projects board.

    Opening this stage's PR into the plan branch is compulsory. There is no
    `gh` binary in this session, so use the GitHub MCP server:
    `mcp__github__create_pull_request` with `<branch>` as the base, and
    `mcp__github__merge_pull_request` where §7 allows the merge. If one of
    those calls fails, reach the same GitHub API another way rather than
    skipping the step.

    This is one of the explicit overrides §3 allows, and it covers the finish
    protocol's PR steps too: wherever `.plan/PLAN.md` writes
    `gh pr create --base plan-<slug>` or
    `gh pr merge --squash --delete-branch`, use the MCP equivalent instead.
    Everything else about those steps is unchanged — the base is still pinned
    to the plan branch and never left to default, the merge is still a
    **squash** merge, and the merged stage branch is still deleted afterwards
    (`mcp__github__merge_pull_request` does not delete it, so delete the
    branch as a separate step). A stage whose PR could not be opened is a
    block, recorded per "Recording a block" — never an outcome quietly passed
    over. That record cannot point at a PR that does not exist, so write the
    runbook on the stage branch as usual, push it, and let the
    `.plan/BLOCKED.md` section on the plan branch name the stage branch and
    say plainly that the PR could not be opened, in place of its URL.

    A label write on this proxy replaces the entire label list of whatever
    you're writing to — never call a "set labels" style write with only the
    label you want to add, or every other label already there is silently
    removed.

    9. DO ONLY THIS STAGE.

    Once you've picked a stage in §2, you know about that one stage and
    nothing else.

    - Do not run, prepare, or start any other stage after this one finishes.
      The protocol's final announcement lists the runnable set — report it
      and stop there; running any of it is the next session's job, not yours.
    - Do not retry a failed stage, count attempts, or try a different stage
      instead. If the stage cannot reach a settled state, record the block
      where the protocol says and stop. A person decides what happens next.
    - Do not send a notification of any kind — no email, no message, no
      comment written to be read as one.
    - Do not write to a GitHub Projects board, even if the protocol would
      normally ask for it — it is not reachable from here. Note in the ledger
      that it's outstanding instead.
    - Do not create files, flags, or state beyond what the protocol already
      writes: the ledger row, the stage's notes block, `.plan/BLOCKED.md`,
      and the stage's own artifacts.

<!-- END STAGE-RUNNER PROMPT -->

## Self-check: every binding constraint, and where the contract names it

| Binding constraint | Named in |
|---|---|
| Check out the plan branch before anything else | §1 |
| Pick the next stage yourself, from the ledger's own derived rule | §2 |
| Push the stage branch early, before the bulk of the work | §5 |
| The ledger row is the only completion signal | §6 |
| Never merge into the repository's default branch | §7 |
| A `gate: human` or `gate: local` stage is refused and the refusal recorded | §4 |
| No local files, network, secrets, or toolchains — reachable-from-cloud only | §4, *Where it runs* |
| Assume no permission prompt and no per-action approval | §8 |
| No write to a GitHub Projects board | §8, §9 |

| Deliberately absent | Excluded by |
|---|---|
| Retry loop, attempt counter, "try the next stage anyway" | §9 |
| Any decision about running more than one stage per session | §2, §9 |
| Notification logic of its own | §9 |
| New state, flags, or side files beyond the existing ledger row | §9 |

Nothing here changes the format of `.plan/PLAN.md` or `.plan/LEDGER.md`. The
contract reads both as they already are, and every record it writes is one
the protocol already defines.

## Caveats worth knowing before relying on this

- **Under `merge: manual`, a run produces no visible signal on the plan
  branch.** The plugin README already states the rule for the local driver —
  no stage ever reaches `done` unattended under `merge: manual`, because
  offering a merge is asking a person — and it costs more here. The `doing`
  flip and the stage's evidence live on the stage branch until its PR merges,
  so the plan branch's ledger row still reads `todo` while the PR sits open,
  and a person checking only the ledger cannot tell a
  finished-but-unmerged stage from one that never ran. The pushed stage
  branch and the open PR are the only difference. A plan meant to run this
  way sets `merge: auto`.
- **This contract now decides which stage to run, where the earlier design
  split that decision into a separate, persistent orchestrator session.**
  That session doesn't exist in this design — see
  [`orchestrator-prompt.md`](orchestrator-prompt.md) for what replaced it.
  Folding stage selection in here means every session re-derives the
  runnable set from scratch, which costs nothing extra: the rule was already
  cheap to compute and the ledger is read fresh every time regardless.
- **The stage branch push is not yet measured for this transport.** The
  earlier routine-based design measured (#107) that push, branch creation, PR
  opening, and PR merging all worked unattended with the run's own
  credentials, for a non-default-branch push carrying no other author's
  commits. Whether that holds identically for a cloud session created
  through this newer path is exactly what the next proof of concept, against
  [`poc/`](poc/), is for.
