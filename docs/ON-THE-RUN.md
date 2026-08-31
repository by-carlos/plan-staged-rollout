# On the run — driving a plan from your phone

This page is for someone who has never used this plugin before and wants to
drive a build with nothing but a phone. It explains the vocabulary as it goes,
so you shouldn't need to read anything else first — though the
[plugin README](../README.md) is where those terms are defined in full if you
want the complete picture later.

A quick glossary, since the rest of the page assumes it:

- **A plan** is a big piece of work this plugin has broken into small,
  ordered pieces (**stages**), tracked in a folder called `.plan/` inside your
  repository.
- **The plan branch** is the git branch that folder lives on — its name is
  always `plan-<something>`, chosen when the plan was created.
- **The ledger** (`.plan/LEDGER.md`) is a small table on the plan branch that
  says which stages are done, which is next, and which — if any — are stuck.
  It is the only place that records what actually happened.
- **A cloud session** is a Claude Code session that runs on Anthropic's
  infrastructure instead of your own computer — the kind you get by opening
  [claude.ai/code](https://claude.ai/code) or the Claude mobile app and
  starting a new session, rather than typing `claude` in a terminal. This page
  is about using one of those, from your phone, to run a stage.

## What it does

Normally you run a plan by opening a session on your own computer, once per
stage, and typing `/plan-run <N>`. **On the run replaces "your own computer"
with a cloud session**, so you can do the same thing from your phone with your
computer switched off. The shape stays the same: one stage, one fresh
session, repeated until the plan is finished.

There is no automation stitching the stages together. Each round, you:

1. Open [claude.ai/code](https://claude.ai/code) or the mobile app and start a
   **new** cloud session, pointed at your repository.
2. Tell it to check out the plan branch and run the next stage (the exact
   wording is in [Step 2](#step-2--run-a-stage), below).
3. Wait. The session does that one stage's work — writes the code, opens a
   pull request, merges it into the plan branch, and records the result in the
   ledger — then stops.
4. Check the ledger (or `.plan/BLOCKED.md`) on the plan branch to see what
   happened, and go back to step 1 for the next stage.

That's the whole loop. There is no persistent chat session watching over the
plan, no dashboard, and nothing that fires the next stage for you — **you are
the loop.** Expect to open one new cloud session per stage, by hand, every
time.

> **Read this before you start anything.** A cloud session cannot see your
> computer at all — not its files, not your local network, not any secret
> stored only on it, and not any tool you have installed but haven't
> committed to the repository. If a stage needs something like that, it
> cannot run in the cloud. See
> [What a cloud session cannot reach](#what-a-cloud-session-cannot-reach)
> before you rely on this for a plan that touches local infrastructure.

## What you need first

**A plan, already pushed to GitHub.** This page doesn't create one — build it
the usual way with `/plan-stages` on your own machine, and push the plan
branch it makes.

While you're building it, `/plan-stages` asks how stage pull requests should
be merged. **Choose `auto`** — the stage merges its own pull request once its
checks pass — rather than `manual`. Under `manual`, a stage finishes its work
but leaves its pull request open for you to merge by hand, which defeats the
point of driving this from a phone: you'd have to open a browser and merge it
before the next stage could even start. See
[What it won't do](#what-it-wont-do) for the rest of what `manual` costs you
here.

Already have a plan that chose `manual`? Ask a session to change the plan
flags line in `.plan/PLAN.md` to `merge: auto` and push the change — you don't
have to start the plan over.

You don't need to set up anything else in advance. Earlier versions of this
page described creating one pre-configured "routine" per model your plan
uses, before you could run anything. That step is gone: a cloud session's
model is chosen fresh each time you create it, so there is nothing to
provision up front.

## How to run it

### Step 1 — Open a cloud session

From your phone (or anywhere else), go to
[claude.ai/code](https://claude.ai/code) or open the Claude mobile app, and
start a **new** session. Point it at your repository. If the interface asks
for a starting branch, use your repository's default branch — the session
will check out the plan branch itself, as its first step.

### Step 2 — Run a stage

As the session's first message, tell it:

```
Check out the plan-<slug> branch. Read the contract between the
BEGIN STAGE-RUNNER PROMPT and END STAGE-RUNNER PROMPT markers in
examples/on-the-run/stage-runner-prompt.md and follow it to run
whichever stage is next.
```

Replace `plan-<slug>` with your actual plan branch name — the session doesn't
know it otherwise. Everything else that stage needs to know — how to pick the
next stage, what to do if it's a stage marked `gate: human` or `gate: local`,
how to record what happened — is written into that contract file, committed
in the repository, so you never have to compose or remember a long prompt of
your own. [`stage-runner-prompt.md`](../examples/on-the-run/stage-runner-prompt.md)
is the file, if you want to read it before trusting it with your plan.

### Step 3 — Wait, then check what happened

The session works through the stage on its own — there is nothing more to
tap or approve. When it stops, check the plan branch on GitHub (the ledger
table in `.plan/LEDGER.md`, and `.plan/BLOCKED.md` if it exists) to see what
happened:

- **A new `done` row** — the stage finished. Go back to Step 1 for the next
  one.
- **A `blocked` row, or a new section in `.plan/BLOCKED.md`** — the stage got
  stuck, and the ledger says why. See [If a stage gets stuck](#if-a-stage-gets-stuck).
- **Nothing changed** — the session may still be running, may have died
  before recording anything, or may have refused to start (see the next
  section). Open the session itself and read what it said.

### If a stage gets stuck

**A `gate: human` stage.** The plan marked this stage as needing a person's
judgment or presence — the cloud session will refuse to run it and will say
so in the ledger. Run that one stage yourself, in a normal session on your own
machine, with `/plan-run <N>`. Once it's `done`, go back to Step 1 for the
next stage.

**A `gate: local` stage.** Same refusal, for a different reason: this stage
needs something only your own machine has (see the warning below). Run it
locally the same way.

**A stage recorded `blocked` for any other reason.** The ledger row's notes,
or the `.plan/BLOCKED.md` section, say what went wrong. Nothing retries
itself — read the runbook it left and decide what to do, the same as you
would for a `blocked` stage on your own machine.

## What a cloud session cannot reach

This is the constraint that matters most, and it applies to every stage,
every time, regardless of how the session was started:

> **A cloud session has no access to anything on your computer or your local
> network.** No local files outside the repository, no LAN, no secret stored
> only on your machine, no locally-installed toolchain. Everything a stage's
> work needs has to already be committed to the repository, or otherwise
> reachable *from the cloud* — a public package registry, a cloud API with a
> secret the session can read from somewhere it has access to, and so on.

If a stage in your plan needs local hardware, a LAN-only host, a secret that
only lives on your machine, or a tool only installed there, mark it
`gate: local` when you write the plan (or, if a stage only discovers this
mid-run, have it record a `needs-local` block — see the
[plugin README](../README.md#unattended-runs--scriptsplan_driverpy) for the
exact convention). A cloud session refuses to start a `gate: local` stage, the
same as it refuses `gate: human` — see [If a stage gets stuck](#if-a-stage-gets-stuck).

A cloud session's access to GitHub itself is also narrower than you might
expect, and it's worth knowing before you rely on it:

- **There is no `gh` command inside a cloud session, and no direct GitHub API
  access.** Every GitHub read and write goes through a proxy the platform
  injects, scoped to the one repository the session was pointed at.
- Two sharp edges in that proxy: a search or list call that doesn't take a
  repository argument can reach outside that one repository, and writing a
  label **replaces the issue's or PR's entire label list** — a naive "add
  this label" silently deletes every other label already there.
- **No plugin loads inside a cloud session**, this one included — so there is
  no `/plan-run` command available inside it. That's exactly why the stage
  session is told to follow `.plan/PLAN.md`'s own protocol and the contract
  file directly, rather than run a slash command that isn't there.
- **A GitHub Projects (v2) board is not reachable from inside a cloud session
  at all.** If your plan's stages need to update a project board, that write
  has to happen from outside — a session on your own machine, or a person
  doing it by hand.

## What it won't do

- **It won't run without you.** There's no automation between rounds — see
  [What it does](#what-it-does). Opening the next session is always a step
  you take.
- **It won't do the final merge.** When every stage reads `done` or
  `skipped`, run `/plan-close` yourself (locally, or from one more cloud
  session, if you prefer) to open the plan-to-`main` pull request — and
  merge it yourself, by hand, in every case. Before you click merge, check
  your repository's default merge button is set to **"Create a merge
  commit."** A squash there flattens every stage into a single commit on
  `main`, which is exactly what the non-squash final merge exists to avoid.
- **It won't run a stage marked `gate: human` or `gate: local`.** See
  [If a stage gets stuck](#if-a-stage-gets-stuck).
- **It won't retry anything.** A stage that doesn't finish gets recorded as
  `blocked`, once, and stops there. Nothing tries again on its own.
- **It won't run stages in parallel.** Even if your plan has more than one
  stage runnable at the same time, this loop takes them one cloud session at
  a time.
- **It can't be relied on to reach your phone the moment something happens.**
  There's no notification mechanism of its own — the plan branch, checked by
  you, is the only signal.
- **It can't run a `merge: manual` plan usefully.** Under `manual`, a
  finished-but-unmerged stage and one that never ran look identical from the
  ledger alone, because the stage stops at an open pull request instead of a
  ledger update. Use `merge: auto` for a plan you intend to drive this way.

## Status: not yet proven for this transport

The plugin's earlier cloud mode — hand-provisioned cloud *routines*, fired by
a persistent chat session pasted with an orchestrator prompt — was proven
end to end once, in
[#110](https://github.com/by-carlos/plan-staged-rollout/issues/110): four
stages on a disposable repository, driven from a phone with the computer off,
ending in a verified closeout. That proof is real, but it proved the old
routine-based mechanism, not this one. **Nobody has yet run a real plan
start-to-finish using cloud sessions created this way**, and this page is not
claiming otherwise. The next proof of concept will run against
[`examples/on-the-run/poc/`](../examples/on-the-run/poc/) and update this
section when it passes.

## If you want the details

Both files below are committed here so they can be reviewed and diffed before
you trust them with a real plan:

- [`stage-runner-prompt.md`](../examples/on-the-run/stage-runner-prompt.md) —
  the contract a cloud session follows to pick and run one stage.
- [`orchestrator-prompt.md`](../examples/on-the-run/orchestrator-prompt.md) —
  the full checklist for the human side of the loop above: exactly what to
  type into each new session, and the judgment calls that stay yours.
