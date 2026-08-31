# Orchestrator checklist

In the plugin's local driver, and in the earlier cloud-routine design this
replaces, an **orchestrator** is the thing that decides which stage runs next
and starts it. In this design, that role is yours. There is no persistent
session or automated loop doing it for you — this file is a checklist for the
person running it by hand, from a phone or anywhere else, plus the exact text
to give each new cloud session.

If you haven't read [`docs/ON-THE-RUN.md`](../../docs/ON-THE-RUN.md) yet,
start there — it walks through the same loop for a first-time reader. This
file is the fuller reference: every judgment call spelled out, for someone
about to actually drive a plan this way.

> **Status: not yet proven for this transport.**
> [#110](https://github.com/by-carlos/plan-staged-rollout/issues/110) proved
> an earlier design — hand-provisioned cloud *routines*, fired by a
> persistent chat session pasted with a different orchestrator prompt — end
> to end. That proof predates this design and does not carry over to it. This
> checklist is not claimed proven until a new proof-of-concept run against
> [`poc/`](poc/) passes.

## What changed from the earlier design

The earlier design split the work across two long-lived things: a
pre-provisioned cloud *routine* per model your plan used, and a persistent
chat session carrying a large pasted prompt that fired those routines in a
loop, one round after another, without you re-entering anything.

Neither exists here:

- **No pre-provisioned routine, and nothing to set up per model.** A cloud
  session's model is chosen when you create it, so there's nothing to
  provision in advance — see
  [`docs/ON-THE-RUN.md`](../../docs/ON-THE-RUN.md#what-you-need-first).
- **No persistent chat session holding a loop open.** Each round is a brand
  new, disposable cloud session — the same "fresh session per unit of work"
  principle the rest of this plugin already runs on. You are the thing that
  connects one round to the next, by opening the next session yourself.
- **Stage selection moved into the stage session itself.** The earlier
  orchestrator's biggest job was computing which stage could run next and
  telling a routine exactly which one. Now you just tell a fresh cloud
  session to "run the next stage," and it works that out on its own — see
  [`stage-runner-prompt.md`](stage-runner-prompt.md) §2.

What's left for you is smaller than the old orchestrator prompt, but it's
still real judgment: deciding when to start the next round, recognizing when
a stage needs you instead of a cloud session, and knowing when to stop for
good.

## Two roles, two files

| | [`stage-runner-prompt.md`](stage-runner-prompt.md) | This file |
|---|---|---|
| Followed by | a cloud session | you |
| Knows about | exactly one stage, once it picks one | the whole loop, round to round |
| Does | the stage's actual work | no repository work at all — only starts sessions and reads state |
| Decides which stage runs next | yes, each time it starts | no — it's the session's own job now |

**One more sense of "orchestrator," distinct from both of these.** The
[plugin README](../../README.md) also uses "orchestrator" for a stage
session whose `exec` flag is `subagent(<model>)`, dispatching that one
stage's implementation to a subagent. That orchestrator sits *inside* one
stage, doing that stage's work through someone else. Neither role on this
page is that one.

## Before you start

- **The plan branch is pushed**, with `.plan/PLAN.md` and `.plan/LEDGER.md`
  on it.
- **The plan flags line reads `merge: auto`.** Under `merge: manual`, a
  finished stage leaves its pull request open instead of updating the
  ledger, so a finished-but-unmerged stage and one that never ran look
  identical from the ledger alone. If your plan says `manual`, either change
  it (ask any session to edit the plan flags line in `.plan/PLAN.md` and push
  it) or expect to check each stage's pull request by hand every round, not
  just the ledger.
- **You have a way to read the plan branch from your phone.** The GitHub
  mobile app, or the mobile web view, is enough — you're only ever reading
  `.plan/LEDGER.md` and `.plan/BLOCKED.md`.

## The loop, round by round

### 1. Start a new cloud session

Open [claude.ai/code](https://claude.ai/code) or the Claude mobile app and
create a new session pointed at your repository.

### 2. Give it exactly this, filled in

```
Check out the plan-<slug> branch. Read the contract between the
BEGIN STAGE-RUNNER PROMPT and END STAGE-RUNNER PROMPT markers in
examples/on-the-run/stage-runner-prompt.md and follow it to run
whichever stage is next.
```

Replace `plan-<slug>` with your plan branch's real name. That's the whole
message — the contract file carries everything else the session needs to
know.

### 3. Wait for it to stop

It runs unattended once started — there's nothing to approve or tap. It
stops on its own, either because the stage settled (done or blocked) or
because it hit something the contract tells it to refuse.

### 4. Read the plan branch, not the session's own summary

Whatever the session says in its own reply is not the record — the plan
branch is. Check `.plan/LEDGER.md` and `.plan/BLOCKED.md` fresh, on GitHub,
for what actually got pushed:

| What you see | What it means | What you do |
|---|---|---|
| A new `done` row | The stage finished, PR merged. | Go to step 1 for the next stage. |
| A `blocked` row, reason not `needs-local` | The stage needs a person present, or hit something it couldn't resolve. | If it's a `gate: human` stage, run it yourself locally with `/plan-run <N>`, then resume the loop. Otherwise, read the notes and decide — same as any `blocked` stage. |
| A `blocked` row, reason `needs-local` | The stage needs something only a local machine has. | Run it yourself locally with `/plan-run <N>`, then resume the loop. |
| No change at all | The session may still be running, may have died before pushing anything, or the branch name was wrong. | Open the session and read what happened before starting another. |
| Every stage `done` or `skipped` | The plan's stages are finished. | Go to [Ending it](#ending-it) — closeout and the merge are yours, never a cloud session's. |

### 5. Repeat

Go back to step 1. There's no state carried between rounds except what's on
the plan branch — if you stop for a day and come back, nothing about the
loop has gone stale.

## Ending it

When every stage reads `done` or `skipped`, the loop is over. Run
`/plan-close` — locally, or from one more cloud session if you'd rather —
to have it distill the plan into a final pull request from the plan branch
into your repository's default branch. **You merge that pull request
yourself, by hand, in every case; no session does this for you.** Before you
click merge, check your repository's default merge button is set to
**"Create a merge commit"** — a squash there collapses every stage's history
into one commit, which is exactly what the non-squash final merge exists to
prevent.

## Judgment calls that stay yours

- **When to start the next round.** Nothing pings you. If you want to be
  told the moment a stage finishes, you have to go and look — there's no
  notification mechanism built into this loop.
- **Whether a `blocked` stage is worth stepping in for right now, or later.**
  A cloud session records a block and stops; it never guesses at a fix or
  retries. Reading the runbook and deciding what to do about it is yours,
  exactly as it would be for a `blocked` stage you hit running the plan
  locally.
- **Whether to run two stages that are both currently runnable one after the
  other, or leave one for later.** A single cloud session only ever runs one
  stage per round (see `stage-runner-prompt.md` §2); running a second one is
  just starting another round.
- **Anything a GitHub Projects (v2) board needs.** A cloud session cannot
  reach one at all. If your plan's stages update a board, that has to happen
  from a session on your own machine, or by hand.

## What this loop won't do

Everything in [`docs/ON-THE-RUN.md`](../../docs/ON-THE-RUN.md#what-it-wont-do)
applies here too: no automation between rounds, no retries, no parallel
stages, no reading a dead session's transcript as the source of truth, and no
running a `merge: manual` plan usefully.
