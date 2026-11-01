---
description: Drive every remaining stage of a staged-rollout .plan/ to completion, running each one as a fresh session on this machine. Use when the user says "run the plan", "run the plan locally", "drive the rest of the stages", or "fire off the remaining stages".
argument-hint: (no arguments — drives the plan's runnable stages until a person is needed)
---

# /plan-run-local — drive the whole plan on this machine

**This is not the single-stage command.** `/plan-run-local` runs **every
remaining stage** of the plan, one after another, each as its own fresh
headless Claude Code session on this machine — not in this session. This
session is the **orchestrator**: it starts a driver script in the background,
is woken when the driver needs a person, and acts. To run one stage yourself,
in this session, use **`/stage-run <N>`**; to run them in the cloud instead,
**`/plan-run-cloud`**.

Before doing anything else, show this notice and stop for a yes/no answer:

> **This runs all remaining stages of the plan on this machine, one fresh
> session per stage, until nothing runnable is left or a stage needs you.**
> No stage runs in this session; this session waits, and answers you while
> it does.
>
> - **What it runs.** Stages whose `gate` is `auto`, absent or `local`, each
>   at the model and effort its stage index row books. It skips `human`,
>   `live` and unknown gates and names them for you. A plan with
>   `merge: manual` stops at every stage's merge; `merge: auto` runs
>   hands-off.
> - **Keep this session open and the machine awake.** The driver is a
>   background command of this session. You can ask how the plan is going at
>   any time, here or from your phone through Remote Control.
> - **Stage sessions need their own login.** A session does not hand its
>   login to the commands it runs, so the driver checks
>   `claude auth status` first and stops if stage sessions would not be
>   logged in. `CLAUDE_STAGE_LAUNCHER` can name a wrapper that supplies one.
> - **Permissions.** Stage sessions run in `auto` permission mode with
>   nobody to answer a prompt. If your organisation has turned auto mode
>   off, the driver stops each stage before it does any work and says so.
> - **Usage.** Every stage is a full session on your plan's usage; this
>   session costs little, so Sonnet at low effort is enough for it.
>
> Continue?

Proceed only on an explicit yes. On no, or anything short of a clear yes,
stop here — nothing has been touched yet.

The driver is `${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/scripts/plan_run_local.py`,
called `driver` below (`python`, or `python3` where that is the
interpreter's name). It holds the loop, the refusals of
[`references/remote-driver.md`](../skills/staged-rollout/references/remote-driver.md)
that apply on this machine, the dead-run rule, and its settings; its
docstring is the authority on them. This command adds the orchestration
only. Work through these steps **in order**:

1. **Locate `.plan/`.** Find the `.plan/` directory at the repo root. If it
   is absent from the working tree, you may simply be on `main` while the
   plan lives on its branch: run `git fetch origin`, then look for `plan-*`
   branches, local first, then remote. Exactly one: offer to check it out,
   and the clone **stays** on it for the whole run. Two or more is a hard
   stop. None: tell the user to bootstrap one with
   `/plan-staged-rollout:plan-stages <idea>`.

2. **Refuse a protected branch.** If the checked-out branch is `main`,
   `master`, `release`, `trunk`, `develop`, or the repository's default, stop.
   The driver refuses it too; saying so here costs nothing.

3. **Push the plan branch.** The driver reads the ledger as pushed
   (`origin/<plan branch>`), because a stage's own push is the only
   completion signal. If the plan branch has unpushed commits, push them
   first. A working tree with uncommitted changes to `.plan/` is a hard stop:
   list them; never stash.

4. **Show what will run first:** `driver next`. Name the stage it would
   start with its model, effort and gate, and any gated stages it lists. If
   it reports `complete`, skip to step 8.

5. **Start the driver** with the Bash tool, `run_in_background: true`:
   `driver run` (or `driver run --resume S<N>`, step 6). Say in one line that
   it is running, which stage it starts on, and that the user can ask for
   progress at any time. Then end the turn: the session is woken when the
   driver exits. Never start a second driver while one runs; the driver
   refuses that too (`already-running`).

6. **When woken, read only the driver's last line,** `STATUS: <status> · <message>`.
   Never open a stage's log or transcript: this session's context stays
   flat for the whole plan. Act on the status:

   | Status | What to do |
   |---|---|
   | `plan-complete` | Step 8. |
   | `gated` | Name each gated stage with its gate and `/stage-run <N>`: `human` needs a person present, `live` changes a running system and a person chooses when, an unknown value means the index needs fixing. Step 8. |
   | `waiting` | Nothing is runnable; name the `doing` and `blocked` rows the rest waits on. Step 8. |
   | `stage-blocked` | Tell the user which stage blocked and the first line of its runbook (in the message); the full runbook is the stage's `.plan/BLOCKED.md` section or its ledger notes. **If the block is a merge the stage could not make** (a permission ask rule on `gh pr merge` denies it in a headless session), handle it as a merge below. A blocked `SF` describing a fix is the final review asking: the user runs `/stage-run SF` attended. Otherwise step 8. |
   | `stage-stopped` | The stage stopped short of `done` with no block, its row `doing` or its stage branch pushed: most often a `merge: auto` merge that GitHub or a permission rule refused. Handle it as a merge below; with no open PR, report the message and step 8. |
   | `stage-dead` | Report it as the message says, with the stage's session id and log path from `driver status`. Never write the ledger or guess the outcome. Step 8. |
   | `launch-mismatch` | The stage session started with a different permission mode, model or effort than asked, and was stopped before any work. For auto mode turned off by managed settings, give the two ways on: allow the stage's commands in the project's settings and set `CLAUDE_STAGE_PERMISSION_MODE=manual` (or `dontAsk`), or run the stages yourself with `/stage-run <N>`. When the message names `CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`, say it is set in the environment this session started from and forces every stage into Manual; whether to change it is the user's call. Never try to get around the setting. Step 8. |
   | anything else | `not-logged-in`, `launcher-missing`, `version-too-old`, `bad-setting`, `bad-index`, `no-plan`, `protected-branch`, `branch-changed`, `already-running`: report the message as it is, with the fix it names. Step 8. |

   **A merge the stage could not make.** Look for the stage's open pull
   request into the plan branch (`gh pr list --base <plan branch> --state open`).
   If there is one, show it and ask (`AskUserQuestion`, header `Merge?`); on
   yes, run `gh pr merge <N> --squash --delete-branch` as its own command,
   where the user's own rule prompts them, then go back to step 5 with
   `--resume S<N>`: the stage's preflight sees the merged PR and records the
   row `done`. Where the stage also left a `.plan/BLOCKED.md` section, tell
   the user to delete it once the row reads `done`: this session never
   writes that file, and `plan-close` refuses while it is there. On no,
   report and go to step 8.

   Every status reaches the user's phone through Remote Control's push when
   that is on; write the message so it stands on its own there.

7. **While the driver runs,** answer a progress question from `driver status`
   alone: the stages finished with their outcome, model and effort, and the
   one in flight.

8. **End announcement.** State every stage this run finished and its outcome,
   every stage left and why (gated, blocked, waiting, or not reached), and
   the exact command for each: `/stage-run <N>` for one stage, a fresh
   `/plan-run-local` to carry on. When every stage is `done` or `skipped`,
   say so and point at closeout — **"close out the plan"** or
   **`/plan-staged-rollout:plan-close`**; this command does not run closeout
   itself. It never opens or merges the plan→main pull request: that stays
   a person's action, always.
