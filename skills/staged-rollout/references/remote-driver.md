# Driving stages remotely — the RemoteTrigger contract

How an orchestrator session fires one stage of a plan as a cloud session using
the `RemoteTrigger` tool built into Claude Code, and how it watches the result.
This replaces the retired Python drivers (`scripts/plan_driver.py`,
`scripts/cloud_fire.py`): there is nothing to install and no credential to
maintain — the tool carries the account's own authentication in-process.

Measured 01 Sep 2026 against Claude Code 2.1.240 (see #143 for the full
investigation). Where something below is stated as *likely* rather than
measured, it says so.

## What the orchestrator is

An ordinary interactive Claude Code session, opened by a person, in a clone of
the repository. It prepares the plan branch and `.plan/` exactly as
`/plan-stages` scaffolds them, pushes, and then drives stages one at a time.
It is not a script and not a scheduled job: everything it does is a tool call
the person can watch in the session.

## Firing one stage

1. **Build the stage prompt.** One sentence: run stage `<id>` of plan branch
   `plan-<slug>`, unattended, per `.plan/RUNNER.md`. That file — scaffolded
   into every plan by `/plan-stages` — carries the whole stage-runner
   contract: checkout-first, the gate refusals, the early push, the
   ledger-as-only-signal rule, and the GitHub-MCP substitutions a cloud run
   needs. Plugins do not load in cloud containers, so the prompt must not
   reference any `/plan-*` command; the plan folder carries everything, which
   is why the plan branch must be pushed before anything fires. **Backfill:**
   a plan scaffolded before `RUNNER.md` existed lacks the file — generate it
   from the plugin's `references/templates/RUNNER.md` (fill the placeholders
   and the version marker), commit it on the plan branch, and push, before
   the first fire.
2. **Create a run-once routine as the stage's config container** with
   `RemoteTrigger {action: "create"}`. The body carries the routine name, a
   `run_once_at` timestamp (any future time — it will not be used, see below),
   and a `job_config.ccr` object holding the environment id, the repository as
   a `sources` entry, the stage prompt as the seeded user message in `events`,
   and the stage's `model` from the stage index in `session_context.model`.
   Booking the model this way is measured to work: the probe run reported the
   booked model from inside the container. Whether reasoning **effort** can be
   booked through `session_context` is an open measurement (#125) — until it is
   settled, treat a stage's `effort` column as a reminder the prompt restates,
   not a booking.
3. **Fire it directly** with `RemoteTrigger {action: "run"}`. This is measured
   to start the session immediately and return the new session id
   synchronously. The routine's schedule is never involved — `run` fires even a
   disabled or already-spent routine — so the `run_once_at` value is inert
   scaffolding, not the launch mechanism. (For the curious: the scheduler was
   measured to fire a `run_once_at` booking roughly three minutes late, which
   is why direct `run` is the contract.)
4. **Watch it** with `RemoteTrigger {action: "list_runs"}` (per-run id, title,
   status, timestamps, and the claude.ai link) and
   `{action: "get_run_log", session_id: …}` (a condensed log: provisioning,
   clone, tool calls, errors, permission denials, final result). A run that
   crashed, failed to provision, or never started is directly visible here —
   the orchestrator does not depend on the fired session having written its own
   ledger row to know something went wrong. The pushed
   `.plan/LEDGER.md` stays the sole source of truth for *stage status*; the run
   log is evidence about the *session*, used to decide when to look and what to
   report, never to overwrite what the ledger says.
5. **Hand the person the link.** Every fired stage is a first-class cloud
   session at claude.ai/code — openable, watchable, resumable. Surface the
   session URL as soon as `run` returns it.

## What the orchestrator refuses

The refusals the retired drivers enforced carry over unchanged, and live here
so the contract survives the scripts:

- **`gate: human` and `gate: local` stages are never fired.** A cloud container
  has strictly less access than the local machine. Report the stage and stop in
  front of it.
- **Dependencies must be settled.** Fire a stage only when every stage in its
  `depends` list reads `done` or `skipped` in `.plan/LEDGER.md`. Firing out of
  order is an operator's deliberate choice, never a default.
- **Never drive from a protected branch.** If the current branch is `main`,
  `master`, `release`, `trunk`, `develop`, or the remote's default, stop: stage
  branches are cut from the checked-out branch and, under `merge: auto`, merged
  back into it.
- **The plan→main merge is manual and human-performed, in every mode.** The
  orchestrator opens nothing against `main` and merges nothing into it.

## Known limits

- **Spent routines cannot be deleted programmatically.** A run-once routine
  auto-disables after firing but stays listed; the API has no delete action.
  Cleanup is a manual step at claude.ai/code/routines, and the orchestrator
  should say so when a plan finishes.
- **Cloud access is a prerequisite.** The `RemoteTrigger` tool's availability
  likely tracks cloud access being enabled on the user's Claude account — an
  account without claude.ai/code cloud has no cloud leg. Likely, not measured
  across account types.
- **Effort booking is unresolved** (#125), as above.

## Why not the alternatives

- **`claude --cloud`** refuses without an interactive TTY and cannot be
  combined with `--print` — nothing scripted or session-driven can call it.
- **The raw session-creation API** (what `scripts/cloud_fire.py` posted to) has
  no native tool, so using it means hand-maintaining an OAuth credential chain.
  That was acceptable machinery to run privately; it is not something a public
  plugin should ship or document.
- **`claude --bg`** spawns local-only background agents, invisible in the
  desktop app and gone with the machine — the opposite of what remote driving
  is for.
