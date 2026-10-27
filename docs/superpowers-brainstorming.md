# Pairing with superpowers brainstorming

[Home](../README.md) · [Install](install.md) · [How it works](staged-rollout.md) · **Brainstorming** · [One or many sessions](single-vs-multi-session.md) · [Cloud runs](ON-THE-RUN.md) · [Tickets](tickets.md) · [Ticket template](ticket-templates.md) · [FAQ](faq.md) · [Reference](reference.md) · [Why](why.md)

**In short:** use the superpowers `brainstorming` skill to settle the design,
then let `plan-stages` turn the result into stages. The design ends up as
**Frozen decisions in `PLAN.md`**, not as a second document. Stop
brainstorming before it hands off to `writing-plans`.

Written against **superpowers 7.0.0**. Version 6.4.1 writes its spec to the
same place and hands off to the same skill, so everything here holds for both.
If a later superpowers release changes where the spec goes or what it hands
off to, the two rules below still apply: one source of truth, and no second
plan.

## Why they fit, and where they collide

superpowers brainstorming is a design conversation: it asks what you want,
plays your answers back, and for a project writes a design document and
waits for your approval. This plugin starts after that point: it splits the
approved design into stages and runs them across sessions.

They collide in two places:

- **The spec file.** Brainstorming writes a design document to
  `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` in your repo and
  commits it. This plugin keeps decisions in exactly one place, the Frozen
  decisions section of `.plan/PLAN.md`, because a second copy is what drifts.
- **The hand-off.** After you approve the document, brainstorming moves on to
  `superpowers:writing-plans`, which writes an implementation plan. A staged
  rollout already has its plan: the stage files under `.plan/`. A second
  plan document would disagree with the first within a stage or two.

## Route 1: let `plan-stages` run it

This is the default and needs nothing from you. When the design is not
settled, `plan-stages` starts with a design pass, using
`superpowers:brainstorming` if the plugin is installed and a built-in short
question flow if not (see [Plan](staged-rollout.md#1-plan--plan-stages-project-idea)).
The command tells the design pass to land its outcome directly as Frozen
decisions in `PLAN.md`, never as a separate spec file.

If you see brainstorming start to write a spec file or reach for
`writing-plans` anyway, say so: "put the decisions in `PLAN.md`, no separate
spec and no plan".

## Route 2: brainstorm first, then plan

Use this when the design deserves a conversation of its own, or you want to
brainstorm in a session that is not the planning session (planning needs an
Opus-class model; the brainstorm does not).

1. **Brainstorm normally.** Answer its questions and approve the written
   design when it is ready.
2. **Stop there.** When it moves to `writing-plans`, tell it to stop: "that is
   all, I will plan this with `plan-stages`".
3. **Start planning.** Run `/plan-staged-rollout:plan-stages` and give it the
   approved decisions as the idea: paste them, or name the spec file and ask
   it to read it. When the decisions are already settled, `plan-stages` skips
   its own design pass and goes straight to splitting the work.
4. **Retire the spec.** Once `PLAN.md` holds the decisions, the spec file is a
   second copy. Delete it in the same commit that adds `.plan/` (it stays in
   git history), or add one line at its top saying it was superseded by
   `.plan/PLAN.md`, and do not edit it again. From then on, a change of mind is
   a change to `PLAN.md`.

Deleting is the cleaner choice. Keeping a marked copy is fine if you want the
conversation's reasoning on hand, since `PLAN.md` records decisions rather
than the discussion behind them.

## Brainstorming inside a stage

A stage can also carry `mode: brainstorm` when it has a real open design
question of its own. That stage runs a design pass first, scoped to the stage,
and it treats the Frozen decisions as settled rather than reopening them. It
is always `gate: human`, because a design pass is a conversation. See
[Reference](reference.md) for the flags.

## Quick rules

| Do | Don't |
|---|---|
| Keep decisions in `PLAN.md` only | Leave the superpowers spec in the repo as a living document |
| Stop brainstorming before `writing-plans` | Let `writing-plans` write a plan next to `.plan/` |
| Brainstorm on any model that suits the conversation | Plan on a model lighter than Opus-class |
| Use `mode: brainstorm` for a stage with its own open design question | Use it on a stage that only needs a one-line plan |

For the other half of the pairing, what running a build as many sessions
changes compared with running it in one, see
[Single session or many](single-vs-multi-session.md).
