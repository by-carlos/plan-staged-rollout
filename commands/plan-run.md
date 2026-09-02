---
description: Drive every remaining stage of a staged-rollout .plan/ to completion, firing each one as a cloud session via RemoteTrigger — one orchestrator session at the keyboard, no stage runs locally. For a single stage in this session, use /stage-run instead.
argument-hint: (no arguments — drives the plan's current runnable set, and keeps going)
---

# /plan-run — drive the whole plan remotely

**This is not the single-stage command.** `/plan-run` fires **every remaining
stage** of the plan, one after another, as cloud sessions on Anthropic's
infrastructure — not in this session, and not just the next one. If you want
to run one stage yourself, in this session, use **`/stage-run <N>`** instead.

Before doing anything else, show this notice and stop for a yes/no answer:

> **This drives all remaining stages of the plan on the cloud, one cloud
> session per stage, until nothing runnable is left or a gate stops it.** It
> does not run any stage in this session. For a single local stage, use
> `/stage-run <N>` instead. Continue?

Proceed only on an explicit yes. On no, or anything short of a clear yes, stop
here — nothing has been touched yet.

This command is a **thin wrapper** around the orchestrator contract in
[`references/remote-driver.md`](../skills/staged-rollout/references/remote-driver.md):
that file is the authority on the `RemoteTrigger` fire shape, the poll cadence,
the dead-run definition, and every refusal. Don't restate or duplicate it here
— locate the plan, drive it stage by stage per that contract, and add only the
loop and reporting below.

Work through these steps **in order**, after the notice above is confirmed:

1. **Locate `.plan/`.** Find the `.plan/` directory at the repo root. If it is
   absent from the working tree, do **not** conclude there is no plan — you may
   simply be on `main` while the plan lives on its branch. Run
   `git fetch origin`, then look for `plan-*` branches: local first, then
   remote. If exactly one exists, offer to check it out (that makes `.plan/`
   appear) and continue from there — the clone then **stays** on the plan
   branch for the rest of this run, exactly as `/stage-run` requires. Two or
   more matches is a hard stop: there is no way to guess which plan was meant.
   If none exists anywhere, stop and tell the user to bootstrap one —
   "bootstrap a plan for \<idea>", or the explicit command
   `/plan-staged-rollout:plan-stages <idea>`.

2. **Refuse a protected branch.** If the checked-out branch is `main`,
   `master`, `release`, `trunk`, `develop`, or the repository's default, stop —
   this command drives from the plan branch, never from one it would push
   stage or merge work into by accident.

3. **Confirm the plan branch is pushed, and back-fill `RUNNER.md` if it's
   missing.** A cloud-fired stage reads `.plan/RUNNER.md` cold, with no plugin
   loaded — nothing here helps it. If the plan branch has unpushed commits,
   push them first. If `.plan/RUNNER.md` is absent (a plan scaffolded before it
   existed), generate it from the plugin's
   `skills/staged-rollout/references/templates/RUNNER.md`, fill its
   placeholders and version marker, commit it on the plan branch, and push —
   before firing anything.

4. **Compute the runnable set.** Read `.plan/PLAN.md`'s stage index and
   `.plan/LEDGER.md`, and derive every `todo` stage whose `depends` are all
   `done` or `skipped`, per `PLAN.md`'s *Runnable set & waves*. If nothing is
   runnable because every stage is `done`/`skipped`, skip straight to step 8.
   If nothing is runnable because everything left is blocked on a `doing` or
   `blocked` row, report that and stop — there is nothing this command can
   fire.

5. **Fire the runnable set, one stage at a time.** For each stage in the
   runnable set, in index order:
   - **`gate: human` or `gate: local`** — never fire it. Report the stage and
     why (a person needs to be present, or the stage needs a resource only the
     local machine has), and move on to the next stage in the set without
     firing this one. Naming it here is the point: a person reading this
     session picks it up with `/stage-run <N>` themselves.
   - **`gate: auto`** — fire it per `remote-driver.md`'s *Firing one stage*:
     build the one-sentence stage prompt naming the plan branch and stage id,
     create the run-once routine carrying the stage's `model` from the index,
     fire it with the `run` action, and surface the returned session id and
     its claude.ai link immediately.
   - Fire stages in the runnable set **sequentially, not concurrently** — one
     `run` call, watched to settlement, before the next. `remote-driver.md`'s
     poll cadence and dead-run rules exist per fired session; running several
     at once multiplies what this command would need to track with nothing in
     the contract that says it's safe to.

6. **Watch each fired stage to settlement**, per `remote-driver.md`'s *When a
   fired run doesn't settle*: poll `list_runs` and re-read `.plan/LEDGER.md`
   together every 3–5 minutes; the moment `list_runs` reports the run ended,
   re-read the ledger immediately, and if the row hasn't moved, wait a further
   10 minutes before re-reading once more. A row that settles `done` moves this
   loop to the next stage in the set. A row that settles `blocked` is reported
   — name the stage, quote its `.plan/BLOCKED.md` section, and continue with
   the rest of the runnable set; a blocked stage does not stop stages that
   don't depend on it. A run that stays dead past the grace period is reported
   exactly as `remote-driver.md` prescribes — session id, link, what
   `get_run_log` showed, and what was actually left behind — and this command
   stops entirely: it never writes to the repository or guesses at the
   outcome on the stage's behalf.

7. **Loop.** Once every stage fired this round has settled, check whether
   this round fired anything: if every stage in the runnable set was
   `gate: human`/`gate: local` and none was fired, stop here and go straight
   to step 8 — recomputing the runnable set would produce the identical set
   forever, since a gated stage that is never fired never leaves `todo`.
   Otherwise recompute the runnable set (step 4) — a stage that just went
   `done` may have unblocked others — and repeat from step 5. Keep going
   until either nothing remains runnable, a round fires nothing, or a step
   above has stopped the command outright.

8. **End announcement.** When the loop ends, state explicitly:
   - Every stage this run fired and its outcome (`done`, `blocked`, or a dead
     run), and every `gate: human`/`gate: local` stage it found and skipped
     over, each with the `/stage-run <N>` a person needs to run.
   - If every stage is now `done` or `skipped`, say so and point at closeout —
     **"close out the plan"** or **`/plan-staged-rollout:plan-close`**.
   - Otherwise, exactly what is left runnable, blocked, or gated, so a rerun of
     `/plan-run` — or a person picking one stage up with `/stage-run <N>` — has
     something concrete to act on.
   Then stop. This command never opens or merges the plan→main pull request in
   any case — that stays a person's action, always.
