# Reference

[Home](../README.md) · [Install](install.md) · [Staged rollout](staged-rollout.md) ·
[Cloud runs](ON-THE-RUN.md) · [Tickets](tickets.md) · [FAQ](faq.md) ·
**Reference**

Look things up here. For how the pieces fit together, read
[How a staged rollout works](staged-rollout.md) first.

- [Plan files](#plan-files)
- [Statuses](#statuses)
- [Stage flags](#stage-flags)
- [Plan flags](#plan-flags)
- [Defaults](#defaults)
- [Why `model` and `effort` are hints, not automation](#why-model-and-effort-are-hints-not-automation)
- [Names](#names)
- [The ledger, kept slim](#the-ledger-kept-slim)

## Plan files

Everything lives in `.plan/` at the repo root, committed on the plan branch.

| File | What it holds | Written by |
|---|---|---|
| `README.md` | Entry point: what the plan is and how to run a stage | `plan-stages` |
| `PLAN.md` | Architecture, **frozen decisions**, the stage index with each stage's flags, the plan flags line, and the operating protocol every stage follows. The single source of truth. | `plan-stages`; a stage changes it only when a frozen decision changes |
| `LEDGER.md` | A one-line-per-stage status table, plus a notes block per stage: acceptance output, as-built detail, gotchas, handoff notes | every stage, at the end of its session |
| `stage-N-<slug>.md` | One stage: its goal, steps as checkboxes, and its acceptance check | `plan-stages`, or the review stage for a follow-up stage |
| `stage-f-review.md` | The final review stage, `SF` | `plan-stages` |
| `RUNNER.md` | What a cloud session follows to run one stage, since plugins don't load in the cloud | `plan-stages`; backfilled for older plans before their first cloud run |
| `BLOCKED.md` | A `### S<N>` section per stage that blocked mid-run, so the block shows on the plan branch before the stage PR merges | a stage that blocks mid-run; nothing clears it automatically |

## Statuses

| Status | Meaning | What happens next |
|---|---|---|
| `todo` | Not started | Runs once every stage in its `depends` is `done` or `skipped` |
| `doing` | Started, not finished: ticked checkboxes and a handoff note | `stage-run <N>` resumes from the unticked boxes |
| `done` | The acceptance check ran, its output is in the ledger, and the stage PR is merged | Stages that depend on it can run |
| `blocked` | Waiting on a person or an outside gate. The stage becomes a runbook of exact steps. A stage that finds mid-run that it needs the local machine uses the literal reason `needs-local`. | You do the steps, then run the stage again |
| `skipped` | Decided against, with a one-line reason | Counts like `done` for `depends`, so nothing deadlocks. If the stage owned a check nothing else covers, its note says so and the review stage reassigns it or accepts the gap. |

A stage left half done is a normal, resumable state, not a failure.

## Stage flags

Each stage declares its own weight in the stage index in `PLAN.md`, so you
don't pay heavy process on trivial work, and don't skimp on the hard parts:

| Flag | Values | Meaning |
|---|---|---|
| `depends` | stage id(s) or `—` | prerequisites that must be `done` or `skipped` first |
| `mode` | `direct` \| `brainstorm` | whether the stage needs a design pass first |
| `exec` | `inline` \| `subagent(<model>)` | where the implementation churn lives |
| `model` / `effort` | launch hints | recommended session weight; checked, not faked |
| `gate` | `auto` \| `human` \| `local` | may the stage be launched with nobody watching? `human` means never — a person's judgment or presence is part of the stage; `local` means never *by a driver running elsewhere* — the stage needs a resource only the local machine has. An unattended runner stops in front of either |

## Plan flags

Two flags apply to the plan as a whole, on the **plan flags** line under the
stage index:

| Flag | Values | Meaning |
|---|---|---|
| `merge` | `manual` \| `auto` | under `auto` the session squash-merges its own stage PR into the plan branch once checks are green, instead of offering it; stage PRs only — the plan→main PR is manual in every mode |
| `plan-dir` | `delete` \| `keep` | what closing does with `.plan/`: remove it as the last commit on the plan branch, or leave it in place for a plan that doubles as documentation |

These two are the plan's **declared defaults**: the answers a session applies
when there is nobody to ask. An interactive session still asks you each one,
with the declared value as its recommendation; `--unattended` is what makes
it apply the default instead of asking. Which questions have a default and
which are hard stops in every mode is in the skill's *Unattended mode*
section ([`SKILL.md`](../skills/staged-rollout/SKILL.md)).

## Defaults

Defaults stay cheap where cheap is safe, and reproduce the fully manual flow:
`direct`, `inline`, a model sized to finish the stage, `gate: auto`,
`merge: manual`, `plan-dir: delete`. A plan that predates these flags needs
no edit.

Raise a stage above the defaults only where it needs it:

- `brainstorm` for genuine open design questions (it also makes the stage
  `gate: human`);
- `gate: local` for a stage that needs a resource only the local machine has;
- `subagent` for a stage with heavy iteration churn;
- `merge: auto` only for a plan you intend to run unattended.

## Why `model` and `effort` are hints, not automation

Launching a *local* stage at its recommended weight is **manual by design,
because the platform gives no other option.** Nothing available to a Claude
Code session can start another local session at a chosen model or effort:

- a session can't switch its own model, so a stage that opens on the wrong
  model can only report the mismatch, not fix it;
- effort **is** readable, from `CLAUDE_EFFORT` in the environment, so the
  protocol checks it rather than merely reminding, but a session still can't
  *change* it, so a mismatch is reported, never corrected;
- the desktop app's suggestion chips, which a finished stage
  [offers](staged-rollout.md#from-a-chip-in-the-desktop-app), carry either
  only a title, a prompt and a working folder (`spawn_task`), or a model and
  effort that may only go *down* from the finishing session's
  (`start_session`). So a chip-started session gets the finishing session's
  model and effort rather than reliably getting the stage's. Chips are also
  desktop-app only; they don't exist in the CLI or on a phone.

Hence the split the protocol uses: **check the model and the effort** (both
readable from the session; an unset `CLAUDE_EFFORT` is reported, not treated
as a mismatch), and hand you the exact command plus its
recommended weight at every handoff. `.plan/` carries that recommendation
because it is the only channel that survives across sessions and works
everywhere the plugin does.

The cloud path is the partial exception: a
[fired cloud stage](ON-THE-RUN.md#under-the-hood) has its `model` booked from
the stage index when it is fired, and that booking is measured to take
effect. Booking `effort` remotely is still an open question (#125), so the
effort column stays a reminder that the stage prompt restates in every mode.

## Names

| Thing | Name |
|---|---|
| Plan branch | `plan-<slug>` |
| Stage branch | `plan-<slug>-s<N>` (flat: git can't nest a branch under an existing branch name) |
| Stage worktree | `../<repo>-s<N>`, a sibling of your clone |
| Stages | `S0`, `S1`, … in dependency order; `SF` is the final review |
| Run the review stage | `stage-run f` |

## The ledger, kept slim

Every stage session reads the ledger, so its size taxes every future session.
It is therefore split in two:

- a **status table**, strictly one line per stage
  (`Stage | Status | Verified | Date | Result`), so "which stage can run next"
  is trivial to find for you and the agent;
- a **notes section**, one block per stage, for as-built detail, acceptance
  output, gotchas and handoff notes. Sessions read only the blocks of the
  stages they depend on.

This split came from field experience: in the pilot rollout the detailed notes
lived inside table cells, and by stage 5 a single row had grown to about 500
words that every later session re-read. The method's token promise only holds
if the ledger stays on a diet.
