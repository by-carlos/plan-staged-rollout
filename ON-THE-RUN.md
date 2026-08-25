# On the run

Drive a staged rollout from your phone, computer off, by firing one Claude
Code cloud routine per stage. This is the quickstart; the full contracts —
verbatim prompts, every rule, and why — are linked at the bottom.

**Not unattended.** You keep a session open and approve each stage as it
fires. That approval prompt is your only notification — see the first "good
to know" below before you set anything up.

## Before you start

- A plan branch already **pushed**, with `.plan/PLAN.md` and
  `.plan/LEDGER.md` on it. This doc doesn't create a plan — bootstrap and
  push one the normal way first (`/plan-stages`).
- The plan flags line reads **`merge: auto`**. Under `merge: manual` no fired
  stage can ever reach `done` unattended, because offering a merge is asking
  a person.
- The repository's default merge button is **"Create a merge commit"** — the
  final plan→main merge is yours to click by hand regardless, but the button
  needs to be right when you get there.

## One-time setup

For **each model** `.plan/PLAN.md`'s stage index uses, create one cloud
routine:

| Field | Value |
|---|---|
| Repository | this repo, in `job_config.ccr.session_context.sources[].git_repository.url` |
| Model | the matching model, in `job_config.ccr.session_context.model` |
| Prompt | [`stage-runner-prompt.md`](examples/on-the-run/stage-runner-prompt.md), pasted verbatim |
| Tools | leave the default set — don't pin a narrower `allowed_tools` list |

A routine can't change its own model mid-run, and a mismatch turns a stage
into a `blocked` row instead of a finished one — so double-check the model
before the first fire, not after.

## Run it

Start an interactive session (phone or desktop) and paste in
[`orchestrator-prompt.md`](examples/on-the-run/orchestrator-prompt.md)
verbatim. From there it loops on its own: read the plan branch, fire the one
stage that's runnable, wait for the ledger to settle, repeat.

## Good to know

- **Approve each fire individually.** Creating or firing a routine raises a
  permission prompt in the session — that prompt *is* the notification that a
  stage started. Tapping "always allow" is convenient once and silent after:
  a stage firing then looks identical to the session sitting idle.
- **A `gate: human` stage always stops and waits for you.** The orchestrator
  refuses to fire it, no matter what — that stage is yours to run
  interactively, same as any other session.
- **The final plan→main merge is always manual**, in every mode. The
  orchestrator stops when every stage reads `done` or `skipped` and hands
  back; it never opens or merges that PR.
- **A blocked stage ends the run**, even if other stages could still go. The
  orchestrator never retries and never routes around a block — it reports
  what it knows and waits for you.

## Status

Proven end to end: a real phone-driven run fired real stages, refused a
`gate: human` stage correctly, and stopped before the final merge, all from
the pushed plan branch alone ([#110](https://github.com/by-carlos/plan-staged-rollout/issues/110)).

## The full contracts

- [`examples/on-the-run/stage-runner-prompt.md`](examples/on-the-run/stage-runner-prompt.md) —
  what the fired routine actually runs, and every rule behind it.
- [`examples/on-the-run/orchestrator-prompt.md`](examples/on-the-run/orchestrator-prompt.md) —
  what your own session runs, and every rule behind it.
- [`examples/on-the-run/poc/`](examples/on-the-run/poc/) — the plan and
  verification script the end-to-end proof used, if you want to try the whole
  lifecycle on a throwaway repo before trusting it with a real one.
