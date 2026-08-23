---
description: Execute one stage of a staged-rollout .plan/ — locate the stage, follow the project's own PLAN.md protocol, verify launch weight, and hand off to the next stage.
argument-hint: <stage number, or f for the review stage> [--unattended]
---

# /plan-run — execute one stage

Run a single stage of an existing `.plan/`. This command is a **thin wrapper**:
the operating protocol lives in the project's own `.plan/PLAN.md`, so a `.plan/`
works standalone via the one-line prompt "Follow the instructions in
`.plan/stage-N-<slug>.md`". Do **not** restate or duplicate that protocol here —
locate the stage, defer to `PLAN.md`, and add only the ergonomics below.

Stage to run: **$ARGUMENTS**

If `$ARGUMENTS` carries the token **`--unattended`**, this session has nobody
to answer it — it was launched by an unattended runner, or the user is
walking away. The token selects **declared default over ask**, never "proceed
anyway". Strip it before resolving the stage, and honour it in steps 3 and 6
below: a `gate: human` stage is never started, and every question the protocol
would put to a person either has a declared default on `PLAN.md`'s plan flags
line (`merge`) or becomes `blocked` + runbook (the `staged-rollout` skill,
*Unattended mode*, classifies each one; `PLAN.md`'s *Recording a block* says
where that runbook is committed). Without the token, nothing changes —
every gate and offer below works exactly as it always has.

Work through these steps **in order**:

1. **Locate `.plan/`.** Find the `.plan/` directory at the repo root. If it
   is absent from the working tree, do **not** conclude there is no plan —
   you may simply be on `main` while the plan lives on its branch. Run
   `git fetch origin`, then look for `plan-*` branches: local first, then
   remote. If a plan branch exists, offer to check it out (that makes
   `.plan/` appear) and continue from there — the clone then **stays** on the
   plan branch for the life of the plan, because stage work happens in
   per-stage worktrees, never in the clone (`PLAN.md`, protocol step 4).
   Only when no plan branch exists
   anywhere, stop and tell the user to bootstrap one — "bootstrap a plan for
   \<idea>", or the explicit command `/plan-staged-rollout:plan-stages <idea>`.
   **Unattended**, the checkout is the declared default when exactly one
   `plan-*` branch matches, so take it without asking; two or more is a hard
   stop, because there is no way to guess which plan was meant.
   Then resolve `$ARGUMENTS` to the stage file `.plan/stage-<N>-<slug>.md` by
   matching the leading `stage-<$ARGUMENTS>-` token — a digit for an
   implementation stage, or `f` for the final review stage
   (`stage-f-review.md`). If nothing matches, stop and list the stage files that
   do exist so the user can pick a valid one.

2. **Defer to the project protocol.** Read `.plan/PLAN.md` and follow its
   **Operating protocol** verbatim for this stage — starting with its
   **Preflight & sync** block (protocol step 0) before reading any status or
   touching any branch; the ledger may only be trusted after it passes.
   Read-scope, dependency gate,
   `mode`/`exec` handling, scope discipline, and the finish protocol all come
   from that file, not from this command. `PLAN.md` is the single source of
   truth; this wrapper never overrides it. That includes the plan-level
   `merge` flag on the plan flags line under the stage index: the finish
   protocol offers the stage PR's merge under `merge: manual` (or when the
   line is absent) and squash-merges it itself under `merge: auto` once checks
   are green — stage PRs only; the plan→main PR is never this command's to
   merge in any mode.

3. **Weight check (ergonomic add).** Before doing any stage work, compare the
   session against the stage's `model` and `effort` flags in `.plan/PLAN.md`'s
   stage index. Verify the **model** from your own system prompt, checked
   mechanically against the `staged-rollout` skill's **Model weight tiers**
   rubric — not a guess about your own weight. State the recommended
   **effort** as a reminder only — effort is not introspectable, so never
   claim to verify it. If the session is **lighter** than the stage
   recommends, say so plainly and **offer continue or abort** so the user can
   relaunch on a heavier session before any work begins. If the disclosed
   model doesn't recognizably match a tier in the rubric, don't guess — state
   the exact model ID/name and ask the user which tier applies.

   **Gate check (same step, unattended only).** Read the stage's `gate`
   column from the same index row (an absent column reads as `auto`). Under
   `--unattended`, a `gate: human` stage is not started: say plainly that it
   needs a person present, name it, and stop — a runner reading the previous
   stage's end announcement should already have stopped in front of it, so
   this is the backstop, not the mechanism. For a `gate: auto` stage run
   unattended, the weight check's continue/abort offer and the tier question
   have no one to answer them: mark the row `blocked` with the mismatch as
   the runbook, and commit it per `PLAN.md`'s *Recording a block* — this step
   runs before the stage branch exists, so that is a direct commit on the plan
   branch, pushed — then stop. Without `--unattended`, `gate` is
   announced and nothing more — the person at the keyboard *is* the gate.

4. **Dependency gate (ergonomic surfacing of the protocol's rule).** Apply
   `PLAN.md`'s dependency gate for every stage this one `depends` on. If a
   prerequisite is not satisfied, stop and say exactly which one and why — do
   not start the stage.

5. **Resume support.** Check the stage's ledger status in `.plan/LEDGER.md` —
   and, because a mid-stage block never changes that row on the plan branch,
   the `### S<N>` sections of `.plan/BLOCKED.md` too (preflight step 0.5 reads
   both). A `doing` row with a section there is a stage that stopped at a gate:
   its runbook is on the stage branch and its PR, so read those before picking
   the stage back up, and leave the section for the operator to delete. If
   it is already `doing`, this is a resume: enter that stage's existing
   worktree (preflight step 0.4 names it — never check the stage branch out
   in the clone), then pick up from the **unticked** checkboxes in the stage
   file's Steps and honor the handoff note in the stage's ledger notes
   block. If it is `done`, confirm with the user before
   redoing anything — a redo follows the protocol's redo rule (a fresh
   `-redo-<K>` branch from the plan branch tip, never the merged stage
   branch). Under `--unattended` that confirmation has no one to give it, so
   the redo is a hard stop: mark the row `blocked` with the redo request as
   the runbook and commit it per *Recording a block* — the redo branch does
   not exist yet, so that is a direct commit on the plan branch — then stop.
   **One exception:** if this session's own preflight (protocol
   step 0.5) has just recorded this very stage `done` — its PR had been
   merged remotely and the row was still `doing` — the stage is finished, not
   a redo and not a resume: go straight to the end announcement. That holds
   under `--unattended` too, where it is not a hard stop. Otherwise run it
   fresh.

6. **End announcement.** When you stop, state explicitly:
   - The stage's outcome: **finished**, or `blocked`/`doing` — and if not
     finished, exactly what remains (which checkboxes, what it's waiting on).
     For a `blocked` outcome, name **where the record was committed** — the
     plan branch's ledger row, or the stage branch plus the plan branch's
     `.plan/BLOCKED.md` section and the stage PR — so whoever reads this knows
     which branch to look at.
   - The **complete runnable set**: *every* `todo` stage whose `depends` are
     now all `done` or `skipped` — derived from the stage index's `Depends`
     column, per `PLAN.md`'s *Runnable set & waves*. Never announce only the
     first one.
     For each stage in the set, give the fresh-session prompt **"run stage
     \<N> of the plan"** — or the explicit command
     **`/plan-staged-rollout:plan-run <N>`** — and state its recommended
     **model and effort** and its **`gate`** from the stage index. A
     `gate: human` stage in the set needs a person at the keyboard — say so,
     because an unattended runner reading this announcement stops in front
     of it rather than launching it.
   - **Whether they can overlap.** If the runnable set holds more than one
     stage, say plainly that those stages are independent and can be launched
     **concurrently, one stage per fresh session** — that launch is the
     operator's action (N terminals); this session cannot start independent
     sessions and must not try. Say that each one runs in **its own
     worktree** (`../<repo-dirname>-s<N>`, created by that session at
     protocol step 4) while the clone stays on the plan branch — that
     isolation is what makes the overlap safe to launch. If the set holds
     exactly one stage, say that too, so "one stage next" reads as a fact
     about the graph rather than a default.
   - If no stages remain runnable (all `done`/`skipped`), point the user at
     closeout — **"close out the plan"** or **`/plan-staged-rollout:plan-close`**
     — instead. Under `--unattended`, name it as
     **`/plan-staged-rollout:plan-close --unattended`**: closeout runs
     headless too, and an unattended runner picks it up from here.
   Then stop.
