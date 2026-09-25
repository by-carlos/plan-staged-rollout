# Driving stages remotely — the RemoteTrigger contract

How an orchestrator session fires one stage of a plan as a cloud session using
the `RemoteTrigger` tool built into Claude Code, and how it watches the result.
This replaces the retired Python drivers (`scripts/plan_driver.py`,
`scripts/cloud_fire.py`): there is nothing to install and no credential to
maintain — the tool carries the account's own authentication in-process.

Measured 01 Sep 2026 against Claude Code 2.1.240 (see #143 for the full
investigation). Where something below is stated as *likely* rather than
measured, it says so.

**Proven end to end, 01 Sep 2026:** a cold cloud session, given only "run
stage S0 of plan branch plan-proof, unattended, per `.plan/RUNNER.md`",
executed a full stage against a fixture repository in 3.5 minutes fire to
done — checkout-first, preflight, early stage-branch push, real acceptance
evidence in the ledger, PR opened via the GitHub MCP with the base pinned to
the plan branch, `merge: auto` squash-merge, `done` row pushed, next-runnable
set reported and not started.

**Full `/plan-run` loop proven, 25 Sep 2026 (#168):** a four-stage fixture
plan (two dependent `gate: auto` stages, a `gate: human` stage, an auto
closeout) was driven to completion on a disposable repository — each auto
stage fired, watched to a `done` row and followed by the next without a
person, the human stage refused and run interactively, `verify_run.py`
passing 43/43 before the final merge, and the plan→main merge done by hand
as a normal merge leaving every stage as its own commits on `main`. Fire to
`done`: 2, 4 and 4.5 minutes per auto stage. It took one re-fire, for the
checkout-in-prompt gap step 1 now closes.

## What the orchestrator is

An ordinary interactive Claude Code session, opened by a person, in a clone of
the repository. It prepares the plan branch and `.plan/` exactly as
`/plan-stages` scaffolds them, pushes, and then drives stages one at a time.
It is not a script and not a scheduled job: everything it does is a tool call
the person can watch in the session.

## Firing one stage

1. **Build the stage prompt.** Run stage `<id>` of plan branch
   `plan-<slug>`, unattended, effort `<effort>`; the plan lives only on that
   branch, so first run `git fetch origin plan-<slug> && git checkout -B
   plan-<slug> origin/plan-<slug>`, then follow `.plan/RUNNER.md`. **The
   checkout belongs in the prompt, not only in `RUNNER.md`:** a cloud clone
   starts detached on the default branch with only that branch fetched, and
   `RUNNER.md` exists only on the plan branch — so a session told merely "per
   `.plan/RUNNER.md`" cannot read the file that tells it to check out. Measured
   25 Sep 2026 (#168): an Opus stage fetched the plan branch on its own
   initiative, a Sonnet stage found no `.plan/`, concluded the repository was
   unset, and ended in 19 seconds with nothing written. `RUNNER.md` — scaffolded
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
   and a `job_config.ccr` object holding the environment id (**required** —
   measured 25 Sep 2026, `create` without one returns HTTP 400 "job_config must
   set ccr.environment_id"; reuse the id of an environment already in
   `RemoteTrigger {action: "list"}`), the repository as
   a `sources` entry, the stage prompt as the seeded user message in `events`,
   and the stage's `model` from the stage index in `session_context.model`.
   Booking the model this way is measured to work: the probe run reported the
   booked model from inside the container. Whether reasoning **effort** can be
   booked through `session_context` is unmeasured — the earlier scripted path
   found `CLAUDE_EFFORT` empty at every level, so treat a stage's `effort`
   column as a reminder the stage prompt restates ("effort: `<effort>`"), not
   a booking. The driver prints each stage's model and effort on one line
   before firing, so what was requested is on record in the session (#125). Do **not** pin a narrow `allowed_tools` list in
   `session_context`: the default preset includes the tools a stage needs, a
   pinned list that omits one breaks the run silently, and the GitHub MCP
   tools must stay reachable — with no `gh` binary in the run they are the
   only way the compulsory PR step can happen (measured on the routine path,
   #106/#107; a routine is exactly what this fires).

   **Shape measured 1 Sep 2026** from a real routine listing — field names may
   drift:

   ```
   RemoteTrigger({
     action: "create",
     name: "<plan-slug> stage <N>",
     run_once_at: "<ISO-8601 UTC timestamp, e.g. 2026-09-01T12:00:00Z — inert, never actually used>",
     persist_session: false,
     job_config: {
       ccr: {
         environment_id: "<required — reuse one from RemoteTrigger list>",
         events: [
           {
             data: {
               type: "user",
               message: {
                 role: "user",
                 content: "Run stage S2 of plan branch plan-example, unattended, effort: med. The plan lives only on that branch, so first run `git fetch origin plan-example && git checkout -B plan-example origin/plan-example`, then follow .plan/RUNNER.md."
               }
             }
           }
         ],
         session_context: {
           model: "claude-sonnet-5",
           sources: [
             { git_repository: { url: "https://github.com/<owner>/<repo>" } }
           ]
         }
       }
     }
   })
   ```

   followed by

   ```
   RemoteTrigger({ action: "run", trigger_id: "<id returned by create>" })
   ```
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
   report, never to overwrite what the ledger says. Poll on a defined cadence,
   not continuously — see "When a fired run doesn't settle" below.
5. **Hand the person the link.** Every fired stage is a first-class cloud
   session at claude.ai/code — openable, watchable, resumable. Surface the
   session URL as soon as `run` returns it.

## When a fired run doesn't settle

A concrete cadence and a concrete dead-run definition, so "wait, then check
again" is a number, not a judgement call (#122).

- **Poll every 3–5 minutes.** Call `list_runs` and re-read `.plan/LEDGER.md`
  together, on that interval, while the run's `list_runs` status still reads
  as running. Tighter polling burns the session's own turns for no benefit —
  nothing about a stage resolves faster for being checked more often.
- **What "ended" looks like.** A fired session that has finished its work does
  **not** flip `status` away from `active` — measured 25 Sep 2026 (#168), a
  run whose log showed its final `result` 19 seconds after firing still read
  `status: "active"` half an hour later. The end signal is
  `worker_status: "idle"` together with a final `result` event in
  `get_run_log`. Waiting for `status` to change would poll forever.
- **The run ending is not the same as the stage settling.** The moment
  `list_runs` reports the session has ended, re-read `.plan/LEDGER.md`
  immediately. If the fired stage's row now reads `done`, `blocked`, or
  `skipped` (or the block is recorded in `.plan/BLOCKED.md` per the ledger's
  own rules), the stage is settled — proceed as normal. If the row is
  unchanged, do not declare the stage dead yet: a session that has finished
  can still have a push in flight. Wait a further 10 minutes, then re-read
  the ledger once more.
- **Still unmoved after the grace period — the stage is dead.** This is the
  crash-vs-never-started discriminator this file exists to provide: a session
  the run log shows as ended, against a ledger row that never moved, is now
  distinguishable from a stage that simply has not been fired yet. Read
  `get_run_log` for that session to learn *why* — a crash, a provisioning
  failure, a denied permission, an error mid-tool-call — but treat it as
  diagnostic only. It explains the failure to the person; it is never
  evidence the orchestrator acts on, and it never substitutes for, or
  overrides, what `.plan/LEDGER.md` says.
- **Declaring a stage dead is a report, not a write.** The orchestrator's
  refusal to touch the repository (below) holds here exactly as everywhere
  else — it does not write a `blocked` row, a `.plan/BLOCKED.md` section, or
  anything else on the stage's behalf. It stops and reports to the person:
  the session id and its claude.ai link, what `get_run_log` showed, how long
  it has been since the stage was fired, and what was actually left behind —
  whether the stage branch exists on the remote
  (`git ls-remote origin plan-<slug>-s<N>`) and whether a pull request
  against the plan branch is open for it. That mirrors the existing
  `needs-local` reporting pattern (`SKILL.md`, *Statuses and human-gated
  stages*): a specific, checked state handed to the person, not a generic
  "something went wrong."
- **A run still reported as running is not stalled, however long the ledger
  has sat still.** `list_runs` distinguishes an alive session from a dead
  one; a long-running stage is not evidence of anything on its own. Keep
  polling on the same cadence, and if asked, report the elapsed time and the
  last state read — the existing rule for "nothing has moved for a long
  stretch" is unchanged, just now backed by a status the orchestrator can
  actually check instead of a guess.

These numbers — 3–5 minute polling, a 10-minute settlement grace period — are
a field-tested starting point (#122), not a tuned constant. An operator who
finds them too eager or too slow for a given plan's stages is free to adjust
them; nothing here depends on the exact interval, only on there being one.

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
- **It never writes `.plan/LEDGER.md` or `.plan/BLOCKED.md` itself.** Those
  files update only from a fired stage's own push, per `RUNNER.md`'s
  ledger-as-only-completion-signal rule. Whatever the orchestrator observes —
  including a stage it has declared dead — it reports to the person; it never
  records that observation into the plan branch on the stage's behalf.

## Known limits

- **Spent routines cannot be deleted programmatically.** A run-once routine
  auto-disables after firing but stays listed; the API has no delete action.
  Cleanup is a manual step at claude.ai/code/routines, and the orchestrator
  should say so when a plan finishes.
- **Cloud access is a prerequisite.** The `RemoteTrigger` tool's availability
  likely tracks cloud access being enabled on the user's Claude account — an
  account without claude.ai/code cloud has no cloud leg. Likely, not measured
  across account types.
- **Effort booking is unresolved** (#125), as above — and a fired stage's
  weight check does not measure it either: in #168 every fired stage
  reported "model and effort match" without ever reading `CLAUDE_EFFORT`,
  taking the effort from the prompt that restated it.
- **The stage-branch push is proven, not guaranteed.** A fired run's pushes
  are unrestricted only for `claude/`-prefixed branches; any other branch is
  accepted only when it is unprotected, has no other open PR, and carries no
  other author's commits (#104). A `plan-<slug>-s<N>` branch cut from the
  plan branch tip passed exactly this in the measured runs (#107, and the
  01 Sep 2026 proof run), but a protected plan branch or a second open PR
  against the stage branch would still bite.
- **The sandbox does not persist paths outside the primary clone between
  tool calls** (measured in the proof run): a sibling stage worktree can
  vanish mid-stage, taking its worktree metadata with it. Worktree-per-stage
  therefore degrades to branch-per-stage in a cloud run. Harmless when §5's
  early push was honoured — everything of value is on the remote — and a run
  that finds its worktree gone should verify the pushed state and carry on
  in the clone, never re-do pushed work.
- **A fired run cannot delete remote branches** (measured in the proof run:
  `git push origin --delete` returns HTTP 403 from the git proxy). Merged
  stage branches therefore linger on the remote; deleting them falls to the
  orchestrator or a person, as part of plan cleanup.

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
