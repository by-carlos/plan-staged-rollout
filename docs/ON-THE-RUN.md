# On the run — driving a plan from your phone

Historically, plan staged rollout runs on your machine: open a session, run one
stage, close it, repeat. **On the run** moves that work to the cloud. Each stage
runs on Claude Code's cloud against your GitHub repo, so you can drive a whole
build from a chat session on your phone with your computer switched off.

## What it does

You keep one orchestrator chat session open. The session, over and over:

1. Reads your plan from GitHub to work out which stage is next.
2. Asks your permission to start that stage. **You tap approve.**
3. A cloud session runs the stage: writes the code, opens a pull request,
   merges it into the plan branch, and records "done" in the plan.
4. If the stage gets stuck, it writes that down in the plan instead of asking —
   nothing in the cloud can reach you mid-stage.
5. Your session sees the "done" (or the "stuck") in GitHub, and either goes
   back to step 1 or stops and tells you.

It stops when every stage is finished, and hands the last merge to you.

> **You still have to be there.** That approve tap in step 2 is the whole
> reason this isn't hands-off. A cloud session can't start another cloud
> session, so someone has to press the button each round, and that someone is
> you. Expect one tap per stage.

## What you need first

**A plan, already pushed to GitHub.** This page doesn't create one — build it
the usual way with `/plan-stages`, and push the plan branch it makes.

While you're building it, `/plan-stages` asks how stage pull requests should be
merged. **Choose "auto"** — the stage merges its own once the checks pass —
rather than "manual". That single answer is what makes the phone version
possible at all; see [What it won't do](#what-it-wont-do) for why.

Already have a plan that chose manual? Ask a session to switch it to auto
merging and push the change — you don't have to start over.

## How to set it up

### Step 1 — Make one worker per model

Look at the stage table in `.plan/PLAN.md` and its `model` column. Count how
many different models are named — usually one or two. Create one Claude Code
cloud routine for each of them:

- **Repository:** yours.
- **Model:** that model. A running job can't switch models, so getting this
  wrong means the stage stops instead of finishing.
- **Prompt:** copy the text between the `BEGIN STAGE-RUNNER PROMPT` and
  `END STAGE-RUNNER PROMPT` markers in
  [`stage-runner-prompt.md`](../examples/on-the-run/stage-runner-prompt.md), and
  paste it in as-is.
- **Tools:** leave them at the default. Narrowing the tool list breaks the run
  without telling you.

### Step 2 — Start the driver

Open a normal chat session — phone, laptop, anywhere — and paste in the text
between the `BEGIN ORCHESTRATOR PROMPT` and `END ORCHESTRATOR PROMPT` markers
in [`orchestrator-prompt.md`](../examples/on-the-run/orchestrator-prompt.md).

Then tell it your plan branch name, because the prompt doesn't include it.
Something like: `The plan branch is plan-slugify. Go.`

### Step 3 — Tap approve

The driver takes it from there. Each time it wants to start a stage it asks
you, and that request is also how you find out a stage has started — there's no
other notification. If you tap "always allow", you'll stop being told anything.

## What it won't do

- **It won't run without you.** See above — the approve tap is the mechanism,
  not a safety setting you can turn off.
- **It won't do the final merge.** When every stage is done it stops and tells
  you. Merging the finished plan branch into `main` is always yours by hand, in
  every mode. Before you click it, set your repo's merge button to **"Create a
  merge commit"** — a squash there flattens every stage into one commit.
- **It won't run stages marked `gate: human`.** Those are the stages you marked
  as needing a person. The driver refuses to start them, says which one, and
  stops. Run it yourself in a normal session, then tell the driver to carry on.
- **It won't retry anything.** If a stage fails or goes quiet, the driver stops
  and reports what it last saw. It won't try again, skip ahead to another
  stage, or edit anything to unstick it.
- **It won't run stages in parallel.** One at a time, in order, even when two
  could go at once.
- **It can't tell you what went wrong inside a failed stage.** It only sees
  what reached GitHub; it cannot read the cloud session's log. A stage that
  dies quietly looks exactly like a stage that never started, and you'll have
  to go and look yourself.
- **It can't run `merge: manual` plans at all.** Under manual merging, a stage
  finishes but leaves its pull request sitting open, and from GitHub alone a
  finished stage and one that never ran look identical. The driver checks this
  before it starts and refuses, rather than getting stuck halfway through.

## Known rough edges

From the one full run done so far
([#110](https://github.com/by-carlos/plan-staged-rollout/issues/110)):

- **Don't leave two drivers running on the same plan.** Nothing stops you and
  nothing warns you — during the proof run, two sessions drove one plan for
  about 90 minutes before anyone noticed. There's no clean way to retire a
  driver session yet.
- **Don't hand the driver to a cloud session.** It has to be a session you're
  actually looking at, because the approve prompt goes wherever the driver is
  running. Put it in the cloud and nobody's there to tap.
- **Stages landing as separate commits on `main` is still unproven.** The proof
  run's final merge got squashed by accident, which is why the merge-button
  note above exists.

## What's next

- [#116](https://github.com/by-carlos/plan-staged-rollout/issues/116) — start a
  whole build from just an issue number, without a person holding a session
  open round after round.
- [#118](https://github.com/by-carlos/plan-staged-rollout/issues/118) — use
  `claude --cloud` as another way to fire stages, for when you do have a
  computer on.

## If you want the details

Both prompts are committed here so they can be reviewed and diffed, and each
one spells out every rule it carries and why:

- [`stage-runner-prompt.md`](../examples/on-the-run/stage-runner-prompt.md) — what
  a cloud worker runs for a single stage.
- [`orchestrator-prompt.md`](../examples/on-the-run/orchestrator-prompt.md) — what
  your driver session runs.
- [`poc/`](../examples/on-the-run/poc/) — a small four-stage plan and a
  verification script, if you'd rather try the whole thing on a throwaway repo
  before trusting it with real work.
