# FAQ

[Home](../README.md) · [Install](install.md) · [How it works](staged-rollout.md) · [Cloud runs](ON-THE-RUN.md) · [Tickets](tickets.md) · [Ticket template](ticket-templates.md) · **FAQ** · [Reference](reference.md) · [Why](why.md)

Short answers, each with a link to the full story.

**Where things stand:**
[Is my plan saved?](#is-my-plan-saved) ·
[How do I resume?](#how-do-i-resume) ·
[A session died mid-stage](#a-session-died-mid-stage) ·
[A stage says it is blocked on me](#a-stage-says-it-is-blocked-on-me-what-now)

**Changing the plan:**
[Skip a stage](#how-do-i-skip-a-stage) ·
[Add a stage](#how-do-i-add-a-stage) ·
[Change a stage's model or effort](#how-do-i-change-a-stages-model-or-effort) ·
[Undo a stage](#how-do-i-undo-a-stage) ·
[Abandon a plan](#how-do-i-abandon-a-plan)

**Running it differently:**
[Two stages at once](#can-i-run-two-stages-at-once) ·
[Without me at the keyboard](#can-stages-run-without-me-at-the-keyboard) ·
[Stage PRs that merge themselves](#can-stage-prs-merge-themselves) ·
[Without the plugin](#can-someone-without-the-plugin-run-a-stage)

**After and around the plan:**
[What happens to `.plan/` at the end?](#what-happens-to-plan-at-the-end) ·
[Plugin updates mid-plan](#does-updating-the-plugin-disturb-a-plan-in-progress) ·
[A record of how runs went](#can-i-keep-a-record-of-how-runs-went)

**Tickets:**
[Change the ticket template](#how-do-i-change-the-ticket-template) ·
[See a ticket before it is posted](#can-i-see-a-ticket-before-it-is-posted) ·
[Implement, not just guide](#how-do-i-get-claude-to-implement-a-ticket-not-just-guide-me) ·
[Does `work-issue` merge on its own?](#will-work-issue-merge-on-its-own) ·
[Queue tickets](#can-i-queue-tickets) ·
[Ticket or plan?](#should-this-be-a-ticket-or-a-plan)

**Install:**
[Can't find the plugin](#i-cant-find-the-plugin) ·
[No session-start nudge](#a-new-session-doesnt-tell-me-the-next-stage) ·
[Desktop app won't update](#the-desktop-app-wont-update-the-plugin) ·
[Plain language does nothing](#plain-language-doesnt-start-a-command)

## Where things stand

### Is my plan saved?

Yes, once you OK the scaffold commit: `plan-stages` commits `.plan/` on the
plan branch (`plan-<slug>`, where `<slug>` is a short name for the project)
and pushes it. Each stage commits and pushes its ledger update on its own
stage branch, and it reaches the plan branch when that stage's PR merges.
Close the laptop and come back next week: nothing lives only in a session.
`main` sees none of it until you merge the final PR.

### How do I resume?

Open a new session in the repo. The [session-start
nudge](staged-rollout.md#session-start-nudge) lists every stage that can
run, with its exact command; say yes. Without the nudge, read the status
table at the top of `.plan/LEDGER.md` (one line per stage) and run
`stage-run <N>` yourself: for a stage that was stopped halfway, it asks
whether to resume or discard that attempt. A stage someone is running right
now still reads `todo` on the plan branch, because its edits live on its own
branch until its PR merges.

### A session died mid-stage

Run `stage-run <N>` again in a fresh session. It finds what the dead session
left and asks whether to resume or discard that attempt. See [Stopping
halfway](staged-rollout.md#stopping-halfway).

### A stage says it is blocked on me. What now?

It wrote you a runbook: exact steps plus a check, either in the stage's
ledger notes or in its stage PR. Do the steps and run the stage again. If it
blocked midway, also delete its `.plan/BLOCKED.md` section by hand. Details:
[Where a blocked record lands](staged-rollout.md#where-a-blocked-record-lands).

## Changing the plan

### How do I skip a stage?

Skip it through its own stage branch, like any other stage: run
`stage-run <N>` and tell the session to skip it, with a one-line reason. It
sets the row to `skipped`, commits that on the stage branch and opens the
stage PR. Once that PR is merged, `skipped` counts like `done` for the stages
that depend on it. Don't commit `skipped` straight onto the plan branch: with
no merged PR, every stage that depends on it fails its dependency check. If
the stage owned a check nothing else covers, say so in its notes: the review
stage picks that up. See [Statuses](reference.md#statuses).

### How do I add a stage?

A stage is three things: a row in the stage index in `PLAN.md` (with its
flags), a row in the ledger, and a `stage-N-<slug>.md` file. Copy an existing
stage's three pieces under any unused number, put the new index row where it
will run, then run the plugin's
`skills/staged-rollout/scripts/renumber_stages.py --slug <slug>` from the
repo. It renumbers only the stages that have not started, so numbers follow
running order and `SF` stays last; a started stage keeps its number.
Regenerate `.plan/BRIEF.md` in the same commit. The review stage adds a stage
only to fix a failing check it found, with your yes, at most 3 per plan;
other work it finds becomes an issue or a later plan.

### How do I change a stage's model or effort?

Edit that stage's row in the stage index in `PLAN.md`, on the plan branch.
When a session doesn't match its stage, the stage stops before any work and
names what to switch to: change it in the model menu and type **go**.

### How do I undo a stage?

There is no undo command, and `main` is untouched either way.

- **Before its PR merges:** close the PR, then from your clone remove the
  stage worktree (`git worktree remove ../<repo>-s<N>`) and delete the branch
  (`git branch -D plan-<slug>-s<N>`). The plan branch still reads `todo` for
  that stage.
- **After it merges:** the protocol's tool is a **redo**. Run
  `stage-run <N>`, confirm the redo, and it cuts a fresh
  `plan-<slug>-s<N>-redo-<K>` branch from the plan branch tip. Reverting by
  hand is outside the protocol; if you do, set the row back to `todo` in the
  same commit, and check the stages that already depend on it.

### How do I abandon a plan?

There is no command for it, and none is needed: nothing reaches `main` until
you merge the final PR. Stop running stages, close any open stage PRs, then
remove the `../<repo>-s<N>` worktrees (`git worktree remove`) and delete the
plan branch and every `plan-<slug>-s*` branch, locally and on GitHub. If you
used `plan-run`, also clear the spent routines at claude.ai/code/routines.

## Running it differently

### Can I run two stages at once?

Yes, when neither depends on the other. Each stage works in its own worktree
on its own branch, so the sessions don't collide. If two touch the same
files, the second to merge pulls in the first and runs its acceptance check
again. Open one session per stage; the nudge and every finished stage list
what can run side by side. See
[Running stages in parallel](staged-rollout.md#running-stages-in-parallel).

### Can stages run without me at the keyboard?

Yes: `plan-run` fires every remaining stage as a cloud session, one after
another, from one local session that has to stay open. It needs
`merge: auto` on the plan flags line; under the default `merge: manual` each
cloud stage stops with its PR open. Stages marked `gate: human`, `gate: local` or
`gate: live` are never fired. See [Running a plan in the
cloud](ON-THE-RUN.md).

### Can stage PRs merge themselves?

Yes: set `merge: auto` on the plan flags line in `PLAN.md`. Each session then
squash-merges its own stage PR once checks are green. It covers stage PRs
only; the final PR into `main` is always yours. See [Plan
flags](reference.md#plan-flags).

### Can someone without the plugin run a stage?

Yes. The operating protocol is inside the plan's `PLAN.md`, so in a clone
on the plan branch this prompt is enough: "Follow the instructions in
`.plan/stage-N-<slug>.md`" (the review stage is `.plan/stage-f-review.md`).
From a fresh clone or a cloud session, ask it to check out `plan-<slug>`
first and follow `.plan/RUNNER.md`.

## After and around the plan

### What happens to `.plan/` at the end?

`plan-close` offers to delete it as the last commit on the plan branch
(after your OK; unattended, it follows the `plan-dir` flag), so it never
reaches `main`. Nothing is lost: its full history stays in git, and the final
PR body carries the plan's decisions and as-built story. To keep the folder
(for a plan that doubles as documentation), set `plan-dir: keep` on the plan
flags line in `PLAN.md`. See [Close](staged-rollout.md#4-close--plan-close).

### Is GitHub's "Automatically delete head branches" setting safe?

Yes. With it on (`delete_branch_on_merge`), GitHub deletes a PR's branch when
the PR merges. A plan branch is the head of exactly one PR, the final one into
`main`, so it is deleted only once the plan is finished; stage branches are
deleted after their merge anyway. A job with several milestones does not merge
into `main` part-way through one plan: each milestone is its own plan in a
programme, closing through its own final PR. That is why no guard against the
setting exists.

### Does updating the plugin disturb a plan in progress?

Not the protocol: a plan follows the operating protocol scaffolded into its
own `PLAN.md`. An update can change the plugin-side layer around it:
`stage-run`'s model-tier check and handoff chips, the session-start nudge,
and `plan-run`'s orchestrator loop. See [Install and
update](install.md#does-updating-disturb-a-plan-in-progress).

### Can I keep a record of how runs went?

Yes, opt in by setting the environment variable `CLAUDE_EFFORT_LOG` to a file
path. Each `stage-run`, and each `work-issue` run that changes something,
then appends one JSON line: the estimated model tier, the outcome and a
one-line note. With the variable unset, nothing is written. The log lives
outside the repo on purpose, because `plan-close` deletes `.plan/`.

## Tickets

### How do I change the ticket template?

Write a small TOML file that extends the built-in default and states only
what differs, then point `ticket_template` at it. Step by step:
[Customizing the ticket template](ticket-templates.md).

### Can I see a ticket before it is posted?

Always. `create-issue` shows a preview and asks **Post it?** before anything
is posted. Say "dry run" or "just draft" to stop at the preview.

### How do I get Claude to implement a ticket, not just guide me?

Give the ticket an **AI prompt** section. With one, `work-issue` branches,
implements and opens a pull request. Without one, it only guides you. See
[Work a ticket](tickets.md#work-a-ticket--work-issue).

### Will `work-issue` merge on its own?

Never. The push and the merge each ask for their own yes, on every branch.

### Can I queue tickets?

On GitHub, "work 124 after 123" records 124 as blocked by 123 and watches
123 from this session for up to 24 hours, then works 124 once 123 closes as
completed. Keep the session open. It is one session per ticket, so a chain of
three tickets is three sessions.

### Should this be a ticket or a plan?

One to three sessions of work: a ticket. Four or more, with parts that depend
on each other: a plan. See [Tickets](tickets.md).

## Install

### I can't find the plugin

It only runs in Claude Code: the CLI, or the desktop app's **Code** tab. It
does not appear in **Chat**, **Cowork** or claude.ai, and a **cloud** session
doesn't have your locally installed copy either. See
[Where it runs](install.md#where-it-runs).

### A new session doesn't tell me the next stage

The session-start nudge needs `bash`; on Windows, install Git Bash. Without
bash you also lose the `gh-body-guard` ticket check and the opt-in
`tracker-write-guard`. Everything else works:
run `stage-run <N>` yourself.

### The desktop app won't update the plugin

It sometimes misses new releases. Remove the plugin and install it again, or
update from the CLI. See [Update](install.md#update).

### Plain language doesn't start a command

Type the slash form, which always works: `/plan-staged-rollout:stage-run 3`.
See [Where it runs](install.md#where-it-runs) for why this can happen.
