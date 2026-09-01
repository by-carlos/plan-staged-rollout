# Plan-Staged Rollout

**Run big projects as many small sessions — not one huge one.**

A Claude Code plugin that breaks a large build into *stages*, executes each
stage in its own fresh session, tracks progress in an evidence-based ledger,
and keeps every decision in exactly one place so the plan never drifts.

```
/plan-staged-rollout:plan-stages <idea>  →  design + decompose into .plan/ (once)
/plan-staged-rollout:plan-run 3          →  execute one stage in a fresh, cheap session (repeat)
/plan-staged-rollout:plan-close          →  final PR, cleanup, done
```

Each is also model-invocable in natural language once installed — e.g. "run
stage 3 of the plan" — the slash form above is the explicit fallback.

And once a rollout is in progress, you don't have to remember any of it: a
`SessionStart` hook detects the `.plan/` directory and tells a fresh session
which stage is next and at what weight — resuming becomes "open a session and
say yes". In repos without a `.plan/`, the hook stays silent (see
[Session-start nudge](#session-start-nudge) below).

## Install

This plugin is listed on the shared
[`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins)
marketplace, and this repository is also a marketplace in its own right — so
you can install it on its own, without adding anything else first. Pick
whichever of these matches how you use Claude Code.

### Claude Desktop app

No terminal needed. Open the **Plugins** pane (the **+** button next to the
prompt box, then **Plugins**) and click **Add**. Put
`by-carlos/plan-staged-rollout` in the **URL** box — it takes a GitHub
`owner/repo` directly, so there is nothing else to paste — then click **Sync**.

The plugin directory opens on its own once the sync finishes. Plan-Staged
Rollout is under the **Code** tab, with a **+** beside it — click that, and it
is installed.

The same **Plugins** pane is where you later enable, disable or remove it.

### Claude Code CLI

From inside a session:

```
/plugin marketplace add by-carlos/plan-staged-rollout
/plugin install plan-staged-rollout@plan-staged-rollout
```

Or from your shell, without starting a session first:

```bash
claude plugin marketplace add by-carlos/plan-staged-rollout
claude plugin install plan-staged-rollout@plan-staged-rollout
```

### From the shared catalog instead

If you already have the `carlos-plugins` marketplace added, or you want the
other plugins in it, install from there:

```
/plugin marketplace add by-carlos/claude-plugins
/plugin install plan-staged-rollout@carlos-plugins
```

Both routes install the same plugin from the same `release` branch of this
repository. The `@<marketplace>` suffix is the only difference — it names where
you added the listing from, not what you get. `main` is where development
happens; `release` is what installs.

### After installing

There is nothing to configure. Go to a repository with a build too big for one
session and run `/plan-staged-rollout:plan-stages <your project idea>` —
everything the plugin needs after that, it writes into that repository's
`.plan/` folder itself.

Installed plugin commands are namespaced — see the quickstart above for the
exact commands to type. The rest of this README uses the short names
(`plan-stages`, `plan-run`, `plan-close`) for readability. Getting a later
version is [Updating](#updating), further down.

## Where it runs

**This is a Claude Code plugin.** It runs everywhere Claude Code does: the
**Claude Code CLI**, and the **Code** tab of the **Claude Desktop app**. You
can install it from either one — the Desktop app has its own plugin menu, so
you never have to open a terminal. Local and SSH sessions both work.

It is not a claude.ai skill. The Claude Desktop app has three tabs, and only
**Code** runs Claude Code plugins — **Chat** and **Cowork** do not, and neither
does claude.ai itself, so the plugin will not appear in any of them. One more
case worth knowing: a desktop **cloud** session loads plugins from your
claude.ai account rather than from your own machine, so a copy you installed
locally will not be there either.

Two parts of the plugin ask for a little more than a session:

- **The session-start nudge needs `bash`.** The hook ships as a cmd/bash
  polyglot wrapper, so it runs on Linux, macOS and Windows via Git Bash. A
  Windows box without bash simply gets no nudge, and nothing else is affected —
  the commands themselves are model-driven, not shell scripts. See
  [Session-start nudge](#session-start-nudge).
- **Driving stages remotely needs cloud access on your Claude account.** The
  orchestrator session fires each stage as a cloud session through Claude
  Code's built-in `RemoteTrigger` tool — nothing to install, but an account
  without claude.ai/code cloud has no cloud leg. See
  [Driving a plan remotely](#driving-a-plan-remotely--the-orchestrator).

**Typing `/plan-staged-rollout:<command>` always works.** Claude Code can also
start one from plain language ("run stage 3 of the plan"), but only when it has
room to read the command descriptions — on a smaller-context model with a lot
of plugins installed it can fall back to names alone, and plain-language
triggering stops working. This plugin's surface is small, so it is an unlikely
squeeze; if it does happen, use the slash form, or give descriptions more room
with `skillListingBudgetFraction` in your Claude Code settings.

---

## The problem

When you hand an AI a project that is too big for one sitting, the usual
outcome is a single monster session (or a monster plan executed in one):

- **Context blows up.** The window fills with file reads, tool output, and
  dead ends. Compaction re-summarizes it lossily, again and again. Token cost
  grows with everything that came *before*, not with the task at hand.
- **The plan drifts.** Decisions get restated in prompts, plans, and replies.
  Copies diverge; three weeks in, nobody knows which version is true.
- **Progress is opaque.** "Where were we?" means re-reading a transcript.
  There is no glanceable state, and "done" means the model *said* it was done.
- **Undo is surgery.** Everything landed as one tangle of commits (or none).
  Rolling back the last piece of work means picking it apart by hand.

Planning workflows (brainstorming skills, plan mode, spec-driven setups) help
you produce a *good plan* — but they still hand you one big artifact to
execute in one big run.

## The idea

Invert it. Make the *session* the unit of work, and make it small:

1. **Decompose once** into the smallest sensible stages, each with explicit
   dependencies, written as thin files in a `.plan/` folder.
2. **One fresh session per stage.** Each session reads only the frozen
   decisions, its stage file, and a slim ledger — never the whole history.
   Context cannot accumulate across stages because sessions don't share it.
3. **One source of truth.** All durable decisions live in `PLAN.md` and are
   *referenced, never copied*. A decision that exists in one place cannot
   diverge.
4. **An evidence ledger.** A stage is done when its acceptance check *ran* and
   the real output is recorded — not when the model claims success.
   `LEDGER.md` is both the resume point and the cross-session memory.
5. **A branch per stage, in a worktree per stage.** Each stage lands as its
   own PR into the plan branch. Reviewing is small, undoing is a branch
   delete, and one stage's "quick fix" can never contaminate another's
   history. Your clone stays parked on the plan branch the whole time — the
   work happens in sibling worktrees, so the ledger is always in front of you
   and two stages can run at once without fighting over a checkout.

Sessions stay cheap, the plan stays true, progress stays visible, and you can
stop and resume whenever you have time.

## What you get

| Goal | Mechanism |
|---|---|
| **Token reduction** | Fresh session per stage: cost per stage is `O(PLAN.md + stage file + ledger table)`, flat no matter how many stages preceded it. No compaction spiral. |
| **Tracking** | Ledger with fixed statuses and pasted acceptance evidence. "Where were we?" is a 10-line table, not a transcript. |
| **Control** | Sessions stop at stage boundaries. You choose pace and order; PR-per-stage gives you an acceptance gate on every unit. Human-gated work becomes an explicit `blocked` + runbook, never faked progress. |
| **Versioning / undo** | `main → plan-<slug> → plan-<slug>-s<N>`. Undo the last stage = discard its branch, but only before its PR merges into the plan branch — after merge, undo is a revert on the plan branch instead. Stage PRs squash-merge into the plan branch; the final PR merges into `main` with a merge commit, so `main` gets one clean commit per stage while `git log --first-parent main` stays one merge per project. |

---

## How it works

### 1. Bootstrap — `/plan-stages <project idea>`

Runs once. If the design isn't settled, it starts with a design pass
(using `superpowers:brainstorming` when installed, or a built-in lightweight
question flow otherwise) — the outcome lands directly as **frozen decisions**,
not as a separate spec that would become a second source of truth. Then it:

- gates on session weight first: bootstrap is the highest-leverage session of
  a plan, so it requires at least an Opus-class model (verified from the
  session) and recommends medium-or-higher effort (reminded — effort isn't
  introspectable), offering to abort so you can relaunch appropriately;
- decomposes the work into the smallest sensible stages with explicit
  `depends`, putting the keystone (the piece everything needs) as S0;
- appends a standing **final review stage** (see below);
- prints the **wave structure and critical path** derived from `depends`, so
  a fan-out is visible before you start — and so is a plan accidentally
  decomposed into a chain;
- records the fixed git and worktree model (branch-per-stage, worktree-per-stage
  — below); it is not a choice you are asked to make;
- scaffolds `.plan/` and commits it. **No stage is executed during
  bootstrap.** It finishes by saying so explicitly and telling you exactly
  what to run next: the first stage's command and its recommended
  model/effort.

```
<repo>/.plan/
  README.md          # entry point + how to run a stage
  PLAN.md            # architecture, frozen decisions, stage index,
                     #   operating protocol  ← single source of truth
  LEDGER.md          # status table + per-stage as-built notes
  stage-N-<slug>.md  # one thin, self-contained stage each
```

The operating protocol lives *inside the scaffolded `PLAN.md`*, so a `.plan/`
folder is fully portable: anyone can run a stage with the one-line prompt
"Follow the instructions in `.plan/stage-N-<slug>.md`" even without this
plugin installed. The commands are ergonomics, not a dependency.

Want to see what a filled-in scaffold looks like before running bootstrap on
a real project? [`examples/`](examples/) holds a complete `.plan/` for a toy
project captured mid-rollout — a `done` stage with real acceptance evidence
pasted in the ledger, a `doing` stage with ticked checkboxes and a handoff
note — plus a tour of the discipline it demonstrates.

### 2. Execute — `/plan-run <N>` (repeat, one fresh session each)

The session follows the operating protocol in `PLAN.md`:

1. **Flag check.** Each stage recommends a model and effort level. The agent
   can't switch its own model, so these are honest *launch hints*: the model
   is verified from the session itself, the effort is a reminder (it isn't
   introspectable), and on a mismatch it tells you and offers continue/abort.
2. **Read only what's needed.** Frozen decisions + the stage file + the ledger
   table + notes of the stages it `depends` on. Never scan the repo.
3. **Dependency gate.** If a prerequisite isn't `done` or `skipped` in the
   ledger (and merged into the plan branch), stop.
4. **Honor `mode`.** `direct` = one-line plan, implement. `brainstorm` = a
   design pass scoped to this stage first, treating frozen decisions as settled.
5. **Honor `exec`.** `inline` = implement here. `subagent(<model>)` = act as
   orchestrator and dispatch implementation to a subagent so the churn stays
   out of this context.
6. **Scope discipline.** Do only this stage. Work spotted for another stage is
   noted in the ledger and left untouched — it may become a new stage.
7. **Finish protocol.** Run the acceptance check and record the *real output*;
   update the ledger row and notes; amend frozen decisions in `PLAN.md` (and
   nowhere else) if one changed; open the stage PR; announce the stage is
   finished and name **every** stage that is runnable now — each with its exact
   command and recommended model/effort, and whether they can overlap; stop.

**Subtasks and interruption.** Stage steps are checkboxes. If a session must
stop mid-stage (blocked, context getting long, you interrupt), it marks the
stage `doing`, ticks the completed boxes, and writes a handoff note.
Re-running `/plan-staged-rollout:plan-run <N>` (or asking to "run stage \<N>
of the plan" again) resumes from the unticked boxes.

**Statuses:** `todo → doing → done`, plus `blocked` (waiting on a human or an
external gate — the stage becomes a runbook with exact steps for you) and
`skipped` (decided against, one-line reason recorded). Partial completion is a
normal, resumable state, not a failure.

**Where a `blocked` record lands** depends on whether the stage's branch exists
yet, and the plan's own `PLAN.md` states the rule (*Operating protocol →
Recording a block*). A block that fires before the branch exists — the weight
check, a `gate: human`/`gate: local` backstop, a refused redo — is committed straight onto
the plan branch, so it is readable the moment it happens. A block that fires
mid-stage lands on the stage branch, where its runbook rides the stage PR, and
is announced on the plan branch through a `### S<N>` section in
`.plan/BLOCKED.md`. That second write is what makes a mid-stage block visible
without waiting for a merge.

### Session-start nudge

The real friction of a multi-day rollout isn't typing a long command — it's
that a fresh session doesn't know a rollout exists. A `SessionStart` hook
closes that gap: when the repo has a `.plan/` directory, every new session
starts already knowing every runnable stage — any `doing` stage to resume, plus
every `todo` whose `depends` are all `done` or `skipped` — with each stage's recommended
model/effort from the stage index and its exact `/plan-run` command. When more
than one stage is runnable it says so, so a fan-out is visible from the first
line of the session.

Deliberately narrow by design:

- **Zero cost elsewhere.** No `.plan/` at the repo root → the hook emits
  nothing. It only ever speaks in a repo with an active rollout.
- **It offers, never runs.** Execution still belongs to the operating
  protocol in `PLAN.md` — weight check, dependency gate, your go-ahead.
- **Fail silent.** Malformed ledger, missing bash, parse ambiguity → no
  output, exit 0. A session-start hook must never degrade a session.
- **Cross-platform.** The `.cmd` file is a cmd/bash polyglot wrapper, so the
  hook runs on Linux, macOS, and Windows (via Git Bash). Its one real
  dependency is `bash`; a Windows box without it simply gets no nudge — the
  rest of the plugin is unaffected, since the commands are model-driven, not
  shell scripts.

### Parallel stages — reported, not launched

`depends` is a real dependency graph, so a plan often has several stages
runnable at the same time. Every surface that answers "what's next" reports the
whole **runnable set** — every `todo` stage whose dependencies are satisfied —
never just the first:

```
3 stages are runnable right now — none depends on another, so they can be
run concurrently, one per fresh session:

- S1 — Parser       /plan-run 1   (model sonnet, effort low)
- S2 — Renderer     /plan-run 2   (model sonnet, effort med)
- S3 — CLI flags    /plan-run 3   (model haiku,  effort low)
```

Bootstrap prints the wave structure and critical path for the same reason: the
wave count is the fewest rounds the plan can take, and the critical path is the
floor on elapsed time that no amount of parallelism removes.

Two deliberate limits:

- **Waves are derived, never stored.** There is no `wave` or `parallel-group`
  column in the stage index. Waves are a view of `depends`, and a stored copy
  of a single source of truth is exactly what this method exists to prevent.
- **Launching is yours.** A session cannot spawn independent top-level
  sessions, so running a wave in parallel means opening one terminal per stage.
  The plugin tells you what *can* overlap; whether to is your call. The
  [remote orchestrator](#driving-a-plan-remotely--the-orchestrator) removes the
  keyboard from *sequential* runs, not from this — it takes a multi-stage
  runnable set one stage at a time.

What makes that physically safe is worktree-per-stage: each session works in
its own directory on its own branch, so nothing contends for a checkout and no
session can see another's uncommitted work. Four further rules keep the
branches from colliding when they meet at the plan branch:

- **The plan branch is the serialization point.** Stage PRs merge one at a
  time, first come first served. Whoever merges second re-syncs — merge the
  plan branch *into* the stage branch, resolve there, and **re-run the
  acceptance check**, because "mergeable" means no textual conflict, not that
  the stage still passes after the sibling's change. Squash merge makes that
  free, which is why stage branches are never rebased or force-pushed.
- **A sibling's stage branch is not drift.** Preflight used to read any `todo`
  row with a committed stage branch as a crashed session and halt — which
  would stop every parallel session. It now classifies by whose stage the
  mismatch is: drift on *your* stage still stops you; another stage's
  in-flight branch is reported and stepped over.
- **Shared write territory is a `depends` edge.** Two stages that write the
  same files are not independent, whatever the feature graph says. There is no
  separate territory field — a second record of one constraint is a second
  thing to drift — so bootstrap checks for the overlap and adds the edge.
- **The `done` ledger write can race.** Both sessions commit it directly on
  the plan branch: edit after the fast-forward, replay with a rebase if the
  push is rejected, keep both rows on conflict, and never force-push the plan
  branch.

**Subagent fan-out is not a substitute.** Running a whole wave from one
orchestrator via `exec: subagent(<model>)` avoids git concurrency, but it
collapses N stages into one branch, one PR, one ledger row and one acceptance
check — and the orchestrator accumulates every subagent's return, so per-session
cost stops being flat, which is the mechanism this whole method rests on. Use
it *within* a stage for churn; if a wave really is one unit of work, merge
those stages at decomposition time instead.

### 3. Git & worktree model (fixed)

```
main
 └── plan-<slug>                    ← plan branch; .plan/ lives here
      ├── plan-<slug>-s0  → PR → plan-<slug>
      ├── plan-<slug>-s1  → PR → plan-<slug>
      └── ...
plan-<slug> → final PR → main       ← at /plan-close
```

On disk, that means your clone and one sibling directory per running stage:

```
~/src/
  myrepo/        ← your clone, always on plan-<slug>, holds .plan/
  myrepo-s1/     ← worktree, branch plan-<slug>-s1
  myrepo-s3/     ← worktree, branch plan-<slug>-s3   (running concurrently)
```

- **Every stage gets its own branch and PR into the plan branch** — no
  exceptions. Uniformity is the point: it keeps each unit reviewable in
  isolation, and it contains the classic failure where "one small commit"
  quietly becomes twenty commits of fixes bleeding into shared history.
- Branch names are flat (`plan-<slug>-s3`, not `plan/<slug>/s3`) because git
  refs can't nest a branch under an existing branch name.
- Feature-branch plumbing is autonomous: the agent **creates and pushes** stage
  and plan branches without asking, and **opens the stage PR** into the plan
  branch as a compulsory part of finishing a stage. Merges are **offered** and
  happen only on your OK — it never merges on its own, and never pushes to
  `main`. The one carve-out is a plan that sets `merge: auto` (see *Per-stage
  knobs*): that is your OK given in advance for **stage PRs only**, so the
  session squash-merges its own stage PR once checks are green; the plan→main
  PR stays yours in every mode. A stage cannot be marked `done` until its PR
  is merged.
- Merge type is fixed by position: stage PRs into the plan branch are
  **squash-merged** (one commit per stage, merged branch deleted); the final PR
  from the plan branch into `main` is a **normal (non-squash) merge**, so each
  stage lands on `main` as its own distinct commit.
- **Repo settings prerequisite:** the GitHub repo must allow both squash
  merging and merge commits. Recommended defaults: squash message = "Pull
  request title and commit details"; merge-commit message = "Pull request
  title and description" (so the distilled final-PR body lands in the merge
  commit on `main`).
- **Nothing enforces the merge type at the final merge — set the repo's
  default merge button to "Create a merge commit."** The plan-to-main merge is
  the one step no session performs, so it is also the one step the plan cannot
  police: whoever merges gets whatever the repo's default button offers, and a
  default of "Squash and merge" silently collapses every stage into a single
  commit on `main`. The result looks successful — the PR is merged, the files
  are all there — and the per-stage history the non-squash merge exists to
  preserve is simply gone. It is easiest to hit from a phone, where the button
  is tapped without the dropdown ever being opened. Closeout states the
  required merge type in the final PR's body for exactly this reason, but a
  line in a PR body is a reminder, not a control.
- **The clone never leaves the plan branch.** *The clone holds the plan;
  worktrees hold the work.* A stage branch is checked out only in its own
  sibling worktree (`../<repo>-s<N>`), created at stage time from the plan
  branch tip and removed after its PR merges — so `.plan/` stays readable in
  the clone at every moment and the `done` write needs no checkout. If a
  stage worktree still holds uncommitted or unpushed work, it is left alone
  and reported rather than removed; the leftover is flagged by every later
  preflight, and closeout stops on it. A worktree that is merely *left over* —
  its branch merged, nothing unpushed — is cleared by closeout instead of
  blocking it.
- **A fresh worktree contains only tracked files.** Untracked local setup a
  stage needs (`.env`, local config, caches, dependency directories) has to be
  copied in — the stage does that and records what it copied in the ledger.
- Branch-per-stage and worktree-per-stage are the only supported model — both
  are recorded as frozen decisions at bootstrap, not choices offered at that
  time.

### 4. Review — the standing final stage

Bootstrap always appends `SF: plan review` (run with
`/plan-staged-rollout:plan-run f`, or by asking to "run the review stage").
It is the one stage exempt
from the read-scope rule: it reads the *entire* ledger — every note, gotcha,
shortcut, and known gap accumulated across all stages — and sweeps for
stragglers. Crucially, **it catalogs; it never implements.** Each finding
becomes exactly one of:

- **A new stage in this plan** — for follow-up work that belongs to this
  project (a shortcut to reconcile, a config to bring under management). It
  gets a PLAN.md stage index row (with its flags), a ledger row, and a stage
  file, and runs later as a normal `/plan-staged-rollout:plan-run <N>` in its
  own fresh session and branch, like any other stage.
- **A spin-off candidate** — for work that has outgrown this plan (a genuinely
  new project). It's recorded in the ledger and surfaced in the final PR body
  as follow-up work; it does not block closeout. Start it later with its own
  `/plan-staged-rollout:plan-stages`.
- **An explicit "accepted, won't fix"** — with a one-line reason, so the gap
  is a decision instead of a surprise.

Its acceptance check: every loose end in the notes is either a new ledger row
or explicitly closed.

### 5. Closeout — `/plan-close`

Refuses to run until every ledger row is `done` or `skipped` (including the
stages the review spawned) and `.plan/BLOCKED.md` holds no leftover `### S<N>`
section from a stage that was later resolved by hand — nothing clears that
file automatically, so closeout checks it instead of trusting the ledger
alone. Then it:

1. distills `PLAN.md` + the ledger into the final PR body, so the *why* and
   the as-built story survive on `main`;
2. clears the stage worktrees that are finished — merged branch, nothing
   unpushed — and stops on any that still holds work git cannot recover;
3. deletes `.plan/` as the last commit on the plan branch (nothing is lost —
   the full plan history remains in git; keeping it is the `plan-dir: keep`
   option, for a project where the plan doubles as documentation);
4. proposes the PR from `plan-<slug>` to `main`. You review and merge.

It runs headless too — `/plan-close --unattended` applies the plan flags
instead of asking, and a
[remotely driven plan](#driving-a-plan-remotely--the-orchestrator) can run it
as one more fired session once every stage is settled. Merging that final PR is
yours in every mode.

---

## Per-stage knobs

Each stage declares its own weight, so you don't pay heavy process on trivial
work — and don't skimp on the hard parts:

| Flag | Values | Meaning |
|---|---|---|
| `depends` | stage id(s) or `—` | prerequisites that must be `done` or `skipped` first |
| `mode` | `direct` \| `brainstorm` | whether the stage needs a design pass first |
| `exec` | `inline` \| `subagent(<model>)` | where the implementation churn lives |
| `model` / `effort` | launch hints | recommended session weight; checked, not faked |
| `gate` | `auto` \| `human` \| `local` | may the stage be launched with nobody watching? `human` means never — a person's judgment or presence is part of the stage; `local` means never *by a driver running elsewhere* — the stage needs a resource only the local machine has. An unattended runner stops in front of either |

And two flags for the plan as a whole, on the **plan flags** line under the
stage index:

| Flag | Values | Meaning |
|---|---|---|
| `merge` | `manual` \| `auto` | under `auto` the session squash-merges its own stage PR into the plan branch once checks are green, instead of offering it; stage PRs only — the plan→main PR is manual in every mode |
| `plan-dir` | `delete` \| `keep` | what closeout does with `.plan/`: remove it as the last commit on the plan branch, or leave it in place for a plan that doubles as documentation |

These two are the plan's **declared defaults** — the answers a session applies
when there is nobody to ask. An interactive session still puts each one to
you, with the declared value as its recommendation; `--unattended` is what
selects the default over the question. The full classification of which
questions have a default and which are hard stops in every mode is in the
skill (*Unattended mode*).

Defaults are deliberately cheap and reproduce the fully-manual flow: `direct`,
`inline`, the cheaper capable model, `gate: auto`, `merge: manual`,
`plan-dir: delete` — a plan that predates these flags needs no edit. Escalate
only where a stage has genuine open design questions (`brainstorm`, which also
makes it `gate: human`), needs a resource only the local machine has
(`gate: local`), or has heavy iteration churn (`subagent`); opt into
`merge: auto` only for a plan you intend to run unattended.

### Why `model` / `effort` are hints, not automation

Launching a *local* stage at its recommended weight is **manual by design,
because the platform gives no other option.** Nothing available to a Claude
Code session can start another local top-level session at a chosen model or
effort level:

- an agent cannot switch its own model mid-session, so a stage that opens on
  the wrong model can only report the mismatch, not correct it;
- effort is not introspectable at all — a session cannot read its own setting,
  which is why the protocol *reminds* rather than verifies;
- the desktop app's suggested-task chips (the click-to-start notifications)
  carry only a title, a prompt and a working directory — no model or effort
  field — so even the one mechanism that can spawn a session inherits the
  app's current selection rather than the stage's recommendation. Chips are
  also app-only; they don't exist in the CLI.

Hence the split the protocol actually uses: **verify the model** (readable from
the session), **remind about effort** (not readable), and hand the human the
exact command plus its recommended weight at every handoff. `.plan/` stays the
carrier of that recommendation because it is the only channel that survives
across sessions and works everywhere the plugin does.

The remote path is the partial exception:
[a fired cloud stage](#driving-a-plan-remotely--the-orchestrator) has its
`model` booked from the stage index at fire time — that booking is measured to
take effect — while booking `effort` remotely is still an open question (#125),
so the effort column stays a reminder the stage prompt restates in every mode.

## Driving a plan remotely — the orchestrator

Everything above assumes you are at the keyboard, launching one session per
stage. The remote path keeps one session at the keyboard — the
**orchestrator** — and moves the stages off your machine: each one runs as a
cloud session on Anthropic's infrastructure, so the work keeps going after you
close the laptop, and every fired stage is a first-class session at
claude.ai/code that you can open, watch, and resume.

The orchestrator is an ordinary interactive Claude Code session in a clone of
your repo. There is nothing to install and no credential to manage: it fires
stages through **`RemoteTrigger`**, a tool built into Claude Code that talks to
the claude.ai routines API with your account's own authentication handled
in-process. Per stage it creates a run-once routine as the stage's config
container — repository, the stage prompt, and the stage's `model` from the
index — fires it directly with the tool's `run` action (the schedule is never
involved), gets the new session's id and link back synchronously, and then
polls the run's condensed log to see it finish, fail, or crash before firing
the next.

The full contract — prompt shape, refusals, what is measured and what is still
open — is in
[`remote-driver.md`](skills/staged-rollout/references/remote-driver.md). The
short version of the guarantees, which carry over unchanged from the retired
local driver:

- **`gate: human` / `gate: local` stages are never fired** — a cloud container
  has strictly less access than your machine; the orchestrator stops in front
  of them.
- **Dependencies must read `done`/`skipped` in the ledger** before a stage
  fires; out-of-order firing is a deliberate operator choice, never a default.
- **It refuses to drive from a protected branch**, and **the plan→main merge
  stays manual and human-performed in every mode.**
- **The ledger is the only state.** Stop driving whenever you like and pick the
  plan up later — from this or any other session — from what is written down.

Three honest limits. A fired stage runs from a checkout whose *content* is the
plan branch but whose HEAD may read a platform-named branch — the stage prompt
warns the session this drift is expected. Spent run-once routines cannot be
deleted programmatically; they auto-disable but stay listed, and cleaning them
up is a manual step at claude.ai/code/routines. And `RemoteTrigger`'s
availability likely tracks cloud access being enabled on your Claude account —
no claude.ai/code cloud, no remote leg.

**Plugins do not load in cloud containers**, so a fired session has no
`/plan-run` to call. It does not need one: the plan carries its own contract —
`.plan/RUNNER.md`, scaffolded by `/plan-stages`, tells a cold session how to
run one stage, and `.plan/PLAN.md` carries the operating protocol it defers
to. The fired prompt is one sentence pointing at them, which is why the plan
branch must be pushed before anything fires. (A plan scaffolded before
`RUNNER.md` existed gets it backfilled from the plugin's templates — see
[`remote-driver.md`](skills/staged-rollout/references/remote-driver.md).)

### Running it from your phone instead — see `docs/ON-THE-RUN.md`

The orchestrator above is a session on a machine of yours. There is a second
path that needs no machine at all: drive the whole plan from a chat session —
phone included, computer off.
[`docs/ON-THE-RUN.md`](docs/ON-THE-RUN.md) is the quickstart — what it does,
how to set it up, and what it will not do.
[`examples/on-the-run/`](examples/on-the-run/) holds the prompt contracts
themselves. (Both are being rewritten around the `RemoteTrigger` mechanism —
see #127 — and describe the older routine-based setup until that lands.)

## The ledger, kept slim

The ledger is read by *every* stage session, so its size taxes every future
session. It is therefore split:

- a **status table** — strictly one line per stage
  (`Stage | Status | Verified | Date | Result`), machine-greppable, so
  "what's the next runnable stage" is trivial for you and the agent;
- a **notes section** — one block per stage for as-built detail, acceptance
  evidence, gotchas, and handoff notes. Sessions read only the blocks of the
  stages they depend on.

This split came directly from field experience: in the pilot rollout the
detailed notes lived inside table cells, and by stage 5 a single row had grown
to ~500 words that every subsequent session re-read. The method's token
promise only holds if the ledger stays on a diet.

## When *not* to use this

- **Work that fits in one to three sessions.** The scaffold has a floor cost;
  below roughly four sessions of work, just do the work.
- **Exploratory work with no settleable design.** If every session would
  legitimately rewrite the frozen decisions, there is nothing to freeze yet.
- **Work that can't be decomposed.** One giant inseparable step gains nothing
  from a ledger around it.

And two honest limits even when it fits: decomposition quality gates
everything (bad stage boundaries cause cross-stage churn no protocol fixes —
though the review stage catches what leaks), and fresh sessions only know what
was written down (a long session carries tacit context; here, note discipline
replaces it).

## How it compares

| | This plugin | Nearest neighbors |
|---|---|---|
| Plan execution | Fresh session per stage; flat token cost | superpowers `writing-plans`/`executing-plans`, plan mode: one plan document, executed in one session lineage |
| Phase separation | Stages with dependencies, resumable in any valid order | GSD-style plan/execute/verify: separate sessions, but coarse phases, no ledger |
| Cross-session state | Evidence ledger + frozen decisions, plain Markdown in-repo | Continuity-ledger / handoff tools: aimed at continuing *one* task across resets |
| Task tracking | No external tooling; git is the database | spec-kit, task-master, beads: capable, but CLIs/MCP servers/issue graphs to install and learn |

None of the neighbors combine **session-per-stage + evidence ledger +
single-source frozen decisions + per-stage weight knobs** — and the
differentiators here are principles encoded in Markdown, not tooling you have
to adopt. It composes with what you already run: superpowers handles the
within-session process (brainstorming, TDD, verification); this handles the
cross-session structure.

## Anti-patterns this exists to prevent

- Restating decisions in prompts or stage files (copies drift — point at
  `PLAN.md`).
- One giant stage (blows context, can't resume — split it).
- Brainstorming everything (design ceremony on mechanical work — `direct` is
  the default).
- Subagents everywhere (session-per-stage already isolates context — reserve
  them for churn).
- Claiming done without evidence (the acceptance output must actually land in
  the ledger).
- Silent scope creep ("while I'm here…" — note it, spin a stage, move on).
- Skipping the dependency gate (building on an unbuilt prerequisite).

## Provenance

Distilled from a real multi-day homelab rollout (centralized logging + AI
analysis, 8 stages) executed manually with this method before it became a
plugin. That run is where the lessons come from: the ledger diet, the
`blocked`-stage runbook pattern, follow-up stages born from shortcuts, and a
later stage catching a regression an earlier stage introduced — because the
earlier stage's assumptions were written down.

## Roadmap

- Parallel waves in the remote orchestrator (it is sequential today)
- Subagent fan-out for independent sub-steps within a stage
- Progress dashboard rendered from the ledger
- Skill evals (triggering accuracy, protocol adherence)

## Status

**Shipped.** This README is the method document; the skill, the three
commands, and the templates are implemented. They were built with the method
itself — decomposed into a `.plan/` and executed stage by stage in this repo
(the plan folder was removed at closeout, as the method prescribes; its full
history is in git). See [`CHANGELOG.md`](CHANGELOG.md) for what shipped when.

Layout:

```
.
  .claude-plugin/plugin.json
  .claude-plugin/marketplace.json  # lists this repo as its own marketplace
  README.md                      ← you are here
  docs/
    ON-THE-RUN.md                # quickstart: drive a plan from your phone
  skills/staged-rollout/
    SKILL.md                     # method: principles, decomposition guidance,
                                 #   flag heuristics, anti-patterns
    references/templates/        # PLAN.md, LEDGER.md, stage-N.md, stage-f-review.md, README.md
    references/remote-driver.md  # the RemoteTrigger contract for firing stages remotely
  examples/
    uptime-page/.plan/           # worked example: a filled-in scaffold, mid-flight
    on-the-run/                  # prompt contracts for unattended cloud runs
      poc/                     #   end-to-end proof-of-concept plan + verify_run.py
  commands/
    plan-stages.md               # /plan-stages <idea>  — bootstrap .plan/
    plan-run.md                  # /plan-run <N>        — execute one stage
    plan-close.md                # /plan-close          — final PR + cleanup
  hooks/
    hooks.json                   # SessionStart registration
    run-hook.cmd                 # polyglot cmd/bash wrapper (Windows + Unix)
    session-start                # .plan/-aware nudge: next runnable stage
```

## Updating

New versions ship on the `release` branch. A merge to `main` releases nothing.

### Claude Desktop app

Open the **Plugins** pane and select the plugin. Its page shows the version you
have and an **Update** button.

**Do not count on the desktop app noticing a new release.** Its updating has
been inconsistent in testing: a plugin sat on an old version across a release,
with the **Update** button inactive and **Check for updates** reporting nothing
available, days after the new version was out.

So if that page shows a version behind the one you expect, do not wait for it.
Remove the plugin and install it again — a reinstall always lands on the
current version. If you have a terminal, the CLI commands below are the
dependable route.

### Claude Code CLI

Run `/plugin` and open the **Marketplaces** tab. Selecting this plugin's
marketplace gives you **Update marketplace** for a one-off, and **Enable
auto-update**, which has Claude Code refresh the marketplace and its installed
plugins in the background shortly after each session starts. That tab also
tells you which state you are currently in.

Auto-update is worth turning on, and worth checking rather than assuming:
Claude Code enables it by default for Anthropic's own marketplaces, not
necessarily for others. The toggle lives here in the CLI, and the desktop app
has no equivalent — which, with the caveat above, makes the CLI the reliable
way to stay current.

`/plugin marketplace update` does the one-off refresh without opening the tab.
The same two actions from your shell, without starting a session first:

```bash
claude plugin marketplace update
claude plugin update plan-staged-rollout
```

However you update, a new version does not load into a session that is already
running: restart Claude Code, or run `/reload-plugins`.

### Does updating disturb a rollout already in progress?

No. A `.plan/` folder carries its own operating protocol inside the `PLAN.md`
that bootstrap scaffolded, and `/plan-run` is a thin wrapper that defers to it.
A plan therefore keeps running exactly as it was decomposed, whatever version
is installed when you come back to it days later. A new version changes what
the *next* `/plan-stages` scaffolds, not what an in-flight plan does.

[`CHANGELOG.md`](CHANGELOG.md) is what shipped when.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Author

Built by **Carlos Eng** —
[GitHub](https://github.com/by-carlos) ·
[LinkedIn](https://www.linkedin.com/in/carlos-eng/)

## License

[FSL-1.1-ALv2](LICENSE) © Carlos Eng — free for any use except building a
competing commercial product, and each release becomes Apache-2.0 two years
after it is made available. Versions released before this change remain MIT.
