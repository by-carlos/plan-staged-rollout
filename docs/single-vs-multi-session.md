# Single session or many

[Home](../README.md) · [Install](install.md) · [How it works](staged-rollout.md) · [Brainstorming](superpowers-brainstorming.md) · **One or many sessions** · [Cloud runs](ON-THE-RUN.md) · [Tickets](tickets.md) · [Ticket template](ticket-templates.md) · [FAQ](faq.md) · [Reference](reference.md) · [Why](why.md)

**In short:** a single-session build keeps everything in one conversation and
relies on that conversation to remember. A staged rollout cuts the build into
stages, runs each in a fresh session, and relies on files in your repo to
remember. The second costs a fixed setup effort and pays it back on builds
that are big, long-lived or shared. Below about four sessions of work, use one
session.

This page compares the two on the same build. For the single-session side it
uses the superpowers planning and execution skills as the example:
`writing-plans`, then `executing-plans` or `subagent-driven-development`,
which carry a written plan out inside the session you are in. Other
single-session workflows (plan mode, a long hand-driven session) share the
same shape, so the points apply to them too. The two approaches also work
together: see [Pairing with superpowers brainstorming](superpowers-brainstorming.md).

## What changes

| | One session lineage | Many fresh sessions (this plugin) |
|---|---|---|
| **Where the plan lives** | A plan document, executed from start to end by one conversation. | `.plan/` in the repo: one `PLAN.md` with the stage index and Frozen decisions, one file per stage. |
| **What each step starts from** | Everything said so far, in context. | Only what it needs: `PLAN.md`, its own stage file, the ledger table and the notes of the stages it depends on. |
| **Context growth** | Grows with every task. Late tasks run in a crowded context, and the session eventually compacts. | A stage starts small, however many stages came before it, because it never loads their conversations. |
| **After compaction or a restart** | The session carries a summary of what it did. Detail the summary dropped is gone. | Nothing needs carrying: the next session reads the ledger. The session-start hook also fires after a compaction and re-offers the next stage. |
| **Resuming** | Resume the same conversation, if it still exists. | Open any session in the repo. A half-done stage is `doing`, with ticked steps and a handoff note, and any machine can pick it up. |
| **Proof that a step is done** | The conversation says so. | The ledger holds the acceptance output, pasted. A stage is `done` only when that evidence is recorded and its PR is merged. |
| **Model and effort** | One choice for the whole session, or a switch you remember to make. | Each stage recommends its own model and effort, and a session that does not match says so before starting. |
| **Human gates** | You are in the conversation, so you decide when to pause. | A stage can be `gate: human`, and a cloud run never fires it: it waits for you to run that stage yourself. |
| **Concurrency** | Work inside the session can be split across subagents, but one conversation coordinates all of it. | Stages whose dependencies are met form a wave, and a wave can run as several sessions at once, one branch and worktree each. |
| **Undoing** | Revert commits, and rebuild your picture of what happened from the conversation. | A stage is its own branch and PR into a plan branch. Redo, skip or abandon one stage without touching the rest. |

## What it costs

A staged rollout is not free, and the single-session route is simpler when it
fits.

- **Planning is a session of its own,** on an Opus-class model, before any
  work is done.
- **Every stage pays a start-up cost:** reading the plan, checking its
  dependencies, writing its ledger entry and opening a PR.
- **Decomposition quality gates everything.** A bad split causes churn between
  stages that no protocol repairs, although the final review stage catches
  what leaks.
- **A fresh session knows only what was written down.** Notes replace the
  tacit context a long session would have carried, so they have to be good.

That is the **floor cost**. Below roughly four sessions of work, the setup
costs more than it saves: use one session. The same goes for exploratory work
with no design you could write down, and for one inseparable step. The
[full list](why.md#when-not-to-use-this) is on the Why page.

## Choosing

- **One session** fits a build you can hold in one to three sessions, one
  that you will finish in a sitting, or one where the design is still moving.
- **Many sessions** fits a build with four or more sessions of work, parts
  that depend on each other, work you want to stop for days and resume exactly,
  or a build several people or machines touch.
- **Both** is common. Brainstorm in a single session, then let `plan-stages`
  cut the result into stages. Inside each stage the single-session skills still
  apply: the stage itself is a bounded session.

Measured numbers for token cost and elapsed time will be added from the issue
titled "Benchmark superpowers single-session against a staged rollout on one
test case".
