# FAQ

[Home](../README.md) · [Install](install.md) · [Staged rollout](staged-rollout.md) ·
[Cloud runs](ON-THE-RUN.md) · [Tickets](tickets.md) · **FAQ** ·
[Reference](reference.md)

Short answers, with a link to the full story.

**Plans:** [Is my plan saved?](#is-my-plan-saved) ·
[Where were we?](#where-were-we) ·
[What happens to `.plan/` at the end?](#what-happens-to-plan-at-the-end) ·
[Run two stages at once](#can-i-run-two-stages-at-once) ·
[Change a stage's model](#how-do-i-change-a-stages-model-or-effort) ·
[Skip a stage](#how-do-i-skip-a-stage) ·
[Add a stage](#how-do-i-add-a-stage) ·
[Blocked on me](#a-stage-says-it-is-blocked-on-me-what-now) ·
[A session died](#a-session-died-mid-stage) ·
[Undo a stage](#how-do-i-undo-a-stage) ·
[Abandon a plan](#how-do-i-abandon-a-plan) ·
[Let stages merge themselves](#can-stage-prs-merge-themselves) ·
[Run without me](#can-stages-run-without-me-at-the-keyboard) ·
[Run without the plugin](#can-someone-without-the-plugin-run-a-stage) ·
[Plugin updates mid-plan](#does-updating-the-plugin-break-a-plan-in-progress) ·
[Log how runs went](#can-i-keep-a-record-of-how-runs-went)

**Tickets:** [Change the template](#how-do-i-change-the-ticket-template) ·
[See it before it posts](#can-i-see-a-ticket-before-it-is-posted) ·
[Implement, not just guide](#how-do-i-get-claude-to-implement-a-ticket-not-just-guide-me) ·
[Merging on its own](#will-work-issue-merge-on-its-own) ·
[Several tickets in a row](#can-i-queue-tickets) ·
[Ticket or plan?](#should-this-be-a-ticket-or-a-plan)

**Install:** [Can't find the plugin](#i-cant-find-the-plugin) ·
[No start-up nudge](#a-new-session-doesnt-tell-me-the-next-stage) ·
[Desktop app won't update](#the-desktop-app-wont-update-the-plugin) ·
[Plain language does nothing](#plain-language-doesnt-start-a-command)

## Plans

### Is my plan saved?

Yes. `plan-stages` commits `.plan/` on the plan branch (`plan-<slug>`) and
pushes it, and every stage commits its ledger update there. Close the
laptop, come back next week: nothing lives only in a session. `main` doesn't
see any of it until you merge the final PR.

### Where were we?

Open a new session in the repo. The [start-up
nudge](staged-rollout.md#session-start-nudge) tells you every stage that can
run, with its exact command. Without the nudge, read the status table at the
top of `.plan/LEDGER.md`: one line per stage.

### What happens to `.plan/` at the end?

`plan-close` deletes it as the last commit on the plan branch, so it never
reaches `main`. Nothing is lost: its full history stays in git, and the final
PR body carries the plan's decisions and as-built story. To keep the folder
(for a plan that doubles as documentation), set `plan-dir: keep` on the plan
flags line in `PLAN.md`. See [Close](staged-rollout.md#4-close--plan-close).

### Can I run two stages at once?

Yes, when neither depends on the other. Each stage works in its own worktree
on its own branch, so they don't collide. Open one session per stage; the
nudge and every finished stage list what can run side by side. See
[Running stages in parallel](staged-rollout.md#running-stages-in-parallel).

### How do I change a stage's model or effort?

Edit that stage's row in the stage index in `PLAN.md`, on the plan branch.
When a session doesn't match a stage, the stage stops before any work and
names what to switch to: change it in the model menu and type **go**.

### How do I skip a stage?

Set its row in `.plan/LEDGER.md` to `skipped` with a one-line reason, and
commit it on the plan branch. `skipped` counts like `done` for the stages
that depend on it. If the stage owned a check nothing else covers, say so in
its note: the review stage picks that up. See [Statuses](reference.md#statuses).

### How do I add a stage?

A stage is three things: a row in the stage index in `PLAN.md` (with its
flags), a row in the ledger, and a `stage-N-<slug>.md` file. The review stage
adds follow-up stages this way for you. To add one yourself, copy an
existing stage's three pieces and edit them.

### A stage says it is blocked on me. What now?

It wrote you a runbook: exact steps plus a check. Find it in the stage's
notes in `.plan/LEDGER.md`, or in `.plan/BLOCKED.md` if it blocked midway.
Do the steps, then run the stage again. See [Where a blocked record
lands](staged-rollout.md#where-a-blocked-record-lands).

### A session died mid-stage

Run `stage-run <N>` again. If the session had ticked boxes and written a
handoff note, the stage resumes from the unticked boxes. If it finds a stage
branch the ledger doesn't explain, it stops and tells you what it found
instead of guessing.

### How do I undo a stage?

Before its PR merges into the plan branch: discard the stage branch. After:
revert its squash commit on the plan branch. Either way `main` is untouched.

### How do I abandon a plan?

There is no command for it, and none is needed: nothing reaches `main` until
you merge the final PR. Stop running stages, close any open stage PRs, then
delete the plan and stage branches and any `../<repo>-s<N>` worktrees.

### Can stage PRs merge themselves?

Yes: set `merge: auto` on the plan flags line in `PLAN.md`. Each session then
squash-merges its own stage PR once checks are green. It covers stage PRs
only; the final PR into `main` is always yours. See [Plan
flags](reference.md#plan-flags).

### Can stages run without me at the keyboard?

Yes: `plan-run` fires every remaining stage as a cloud session, one after
another, from one local session that has to stay open. Stages marked
`gate: human` or `gate: local` are never fired. See [Running a plan in the
cloud](ON-THE-RUN.md).

### Can someone without the plugin run a stage?

Yes. The operating protocol is inside the plan's `PLAN.md`, so this prompt is
enough: "Follow the instructions in `.plan/stage-N-<slug>.md`".

### Does updating the plugin break a plan in progress?

No. A plan follows the protocol scaffolded into its own `PLAN.md`; an update
only changes what the next `plan-stages` creates. The one exception is
`plan-run`'s orchestrator loop. See [Install and
update](install.md#does-updating-disturb-a-plan-in-progress).

### Can I keep a record of how runs went?

Yes, opt in by setting the environment variable `CLAUDE_EFFORT_LOG` to a file
path. Each `stage-run` and each `work-issue` run that changes something then
appends one JSON line: the estimated model tier, the outcome and a one-line
note. With the variable unset, nothing is written. The log lives outside the
repo on purpose, because `.plan/` is deleted at closing.

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

On GitHub, "work 124 after 123" waits until issue 123 closes, then works 124.
It is one session per ticket, so a chain of three tickets is three sessions.

### Should this be a ticket or a plan?

One to three sessions of work: a ticket. Four or more, with parts that depend
on each other: a plan. See [Ticket or plan?](tickets.md#ticket-or-plan)

## Install

### I can't find the plugin

It only runs in Claude Code: the CLI, or the desktop app's **Code** tab. It
does not appear in **Chat**, **Cowork** or claude.ai. A desktop **cloud**
session loads plugins from your claude.ai account, not your machine. See
[Where it runs](install.md#where-it-runs).

### A new session doesn't tell me the next stage

The start-up nudge needs `bash`. On Windows, install Git Bash. Everything
else works without it: run `stage-run <N>` yourself.

### The desktop app won't update the plugin

It sometimes misses new releases. Remove the plugin and install it again, or
update from the CLI. See [Update](install.md#update).

### Plain language doesn't start a command

Type the slash form, which always works: `/plan-staged-rollout:stage-run 3`.
See [Where it runs](install.md#where-it-runs) for why this can happen.
