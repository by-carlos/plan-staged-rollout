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

From within Claude Code:

```
/plugin marketplace add by-carlos/claude-plugins
/plugin install plan-staged-rollout@carlos-plugins
```

Installed plugin commands are namespaced — see the quickstart above for the
exact commands to type. The rest of this README uses the short names
(`plan-stages`, `plan-run`, `plan-close`) for readability.

The plugin is distributed through the
[`carlos-plugins`](https://github.com/by-carlos/claude-plugins) catalog, which
serves it from this repository's `release` branch. `main` is where development
happens; `release` is what installs. Run `/plugin marketplace update` to pick
up a new version.

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
check, a `gate: human` backstop, a refused redo — is committed straight onto
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
  [unattended driver](#unattended-runs--scriptsplan_driverpy) removes the
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
instead of asking, and the [unattended driver](#unattended-runs--scriptsplan_driverpy)
launches it for you once every stage is settled. Merging that final PR is
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
| `gate` | `auto` \| `human` | may the stage be launched with nobody watching? `human` means never — an unattended runner stops in front of it |

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
makes it `gate: human`) or heavy iteration churn (`subagent`); opt into
`merge: auto` only for a plan you intend to run unattended.

### Why `model` / `effort` are hints, not automation

Launching a stage at its recommended weight is **manual by design, because the
platform gives no other option.** As of August 2026, nothing available to a
Claude Code session can start another session at a chosen model or effort
level:

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

This is a platform limit, not a preference. If session spawning ever gains
model/effort parameters, the handoff step is the place to revisit.

The limit is on what a *session* can do, and that is why the unattended driver
below is a script rather than a skill: outside any session, `claude -p --model
… --effort …` sets both freely. The hint in `.plan/` is still the carrier — the
driver reads the same stage-index columns a person reads, and prints them
before every launch.

## Unattended runs — `scripts/plan_driver.py`

Everything above assumes you are at the keyboard, launching one session per
stage. [`scripts/plan_driver.py`](scripts/plan_driver.py) does that launching
for you: it runs stages back to back, closes the plan out when they are all
settled, and stops when something genuinely needs a person.

**One unattended run covers the whole lifecycle bar two gates.** From a
bootstrapped `.plan/` the driver reaches an open plan→main PR by itself; the
only two places it hands back are a `gate: human` stage and the final merge,
which is yours in every mode.

```bash
python scripts/plan_driver.py --dry-run
```

Run it from the **plan branch clone** (the clone stays parked there for the
life of the plan). It is a re-scanning loop, not a schedule: each round it
reads `.plan/LEDGER.md` and `.plan/PLAN.md`'s stage index, recomputes the
runnable set exactly as `/plan-run` does, launches the next stage as its own
`claude -p "/plan-staged-rollout:plan-run <N> --unattended"` session, waits for
it, and re-reads the ledger. **The ledger is the only state.** Stop the driver
whenever you like and start it again later; it picks up from what is written
down, exactly as a person would.

`--dry-run` computes and prints the whole order — which stages, in which
sequence, at what model and effort, and the exact command each would get —
without launching anything:

```
[plan-driver] launching S1 - CLI runner (model sonnet, effort low, gate auto) - attempt 1 of 2
[plan-driver]   $ claude -p "/plan-staged-rollout:plan-run 1 --unattended" --model sonnet --effort low ...
```

### What stops it

| Stop | What the driver does |
|---|---|
| `gate: human` stage is next | reports it and stops **before** launching — never runs a stage marked as needing a person |
| a stage comes back `blocked` before its branch existed | reports it and stops; the session committed its own runbook to `LEDGER.md` on the plan branch, and the driver never retries a deliberate block |
| a stage blocks mid-stage | same stop, read from the `### S<N>` section the session wrote to `.plan/BLOCKED.md` on the plan branch; the full runbook is on the stage branch and its PR, and the `LEDGER.md` row still reads `doing` until someone merges it |
| a stage does not reach `done` within `--max-attempts` (default 2) | records the stage as blocked, with a runbook, in `.plan/BLOCKED.md` — never in `LEDGER.md`, which the stage's own branch may still be editing unmerged (see below) — commits it on the plan branch (`--no-commit` writes without committing), and stops |
| nothing runnable, stages still open | reports which stages are waiting and stops |
| every stage `done`/`skipped` | launches [`/plan-close --unattended`](commands/plan-close.md) as one more session, then reports the plan→main PR's URL and exits 0 |
| closeout hits one of its own gates | reports that no PR was opened and stops — a stage worktree holding unpushed work is the usual cause |

Exit code is `0` for a completed plan, `1` for any stop that wants a person,
and `2` for a usage or guardrail refusal.

**`.plan/BLOCKED.md` — the block record that isn't the ledger.** A stage that
ran out of attempts, or that stopped itself at a mid-stage gate, has usually
already committed its own edits to `LEDGER.md`'s row and notes, on its own
branch — real acceptance evidence, or a PR that opened but couldn't merge.
Writing a block into those same lines on the plan branch would diverge from
that unmerged commit, leaving the stage's own pull request unmergeable — the
runbook would then be naming a merge its own write had just made impossible.
`.plan/BLOCKED.md` is a sibling file the stage branch never edits, so a write
to it and the stage's own write never contend for the same lines. **Both the
driver and a stage session write there**, for the same reason and in the same
format: the driver when the retry cap is reached, and a session when it blocks
after its stage branch exists (`PLAN.md`, *Recording a block*). Every driver
round treats a stage id listed there as blocked and never retries it, even
across a restart, regardless of what its `LEDGER.md` row still reads.
Resolving the stage — merging its PR, or running
`/plan-run` by hand — does not clear the entry on its own; the file's own
runbook says to delete that stage's `### S<N>` section once the stage is
resolved and then start the driver again. After a hand merge the row keeps
reading `doing` until a session's preflight records the merged PR as `done`
— the next session the driver launches does exactly that, and
[`/plan-run`](commands/plan-run.md) treats a row its own preflight just
self-healed as finished, not as a redo.

### Closeout, unattended

Once every row is `done` or `skipped` the driver launches one final session,
`claude -p "/plan-staged-rollout:plan-close --unattended"`, in the same clone
and with the same profile as the stage sessions. That session applies the
plan's declared defaults instead of asking: it removes any stage worktree
whose branch is merged with nothing unpushed (and stops on any that holds work
git cannot recover), deletes or keeps `.plan/` per the `plan-dir` flag, and
**opens** the plan→main PR. It never merges it.

Closeout has no stage-index row, so its weight comes from the CLI:

```bash
python scripts/plan_driver.py --close-model opus --close-effort medium
```

`--no-close` restores the old behaviour — the driver stops at "plan complete"
and you run `/plan-close` yourself.

The driver confirms the outcome with `gh pr list` against the plan branch, and
distinguishes three results: a URL (closeout succeeded, go and merge it), no
open PR (closeout stopped at a gate — exit 1), and `gh` unable to answer
(reported as unconfirmed rather than as either).

### Guardrails

- **It refuses to run on a protected branch** — `main`, `master`, `release`,
  `trunk`, `develop`, or the remote's default — regardless of what the repo's
  own policy allows. Stage branches are cut from whatever is checked out and,
  under `merge: auto`, merged back into it; a driver pointed at `main` would
  merge stage work straight into it. This refusal has no override flag.
- **The retry cap is a cap, not a hint.** A stage gets `--max-attempts`
  launches (default 2) and is then marked `blocked`. The driver never loops on
  a failing stage, and it never retries a stage its own session marked
  `blocked`.
- **Model and effort are printed before every launch.** Headless spend with
  nobody watching is the real risk here, so the weight of each session is on
  the stream before it starts. `--max-budget-usd` passes a per-session ceiling
  through to `claude` if you want a hard stop as well. Budget for a fixed
  floor per session: measured on the first end-to-end run, a stage session
  loads roughly 50k tokens of system prompt and plugin surface before doing
  any work — $0.20–0.35 on Sonnet — so a plan of many tiny stages is
  overhead-dominated, and the driver pays off on a few substantial stages
  rather than many trivial ones. The driver does not report what a run cost;
  stage sessions inherit the terminal, so there is no usage total to read back.
- **`--plan-dir` is for dry runs only.** Stage sessions run in the checked-out
  repo, so a real run pointed at another repo's `.plan/` would work the wrong
  tree. The driver refuses that combination outright; `--dry-run` still reads
  any plan you point it at.
- **It never merges anything itself.** Stage PRs are merged by their own
  sessions under the plan's `merge` flag; the plan→main PR is manual in every
  mode, driver or no driver.

### The permission profile under `-p`

A `-p` session has nobody to answer a permission prompt, so **any rule that
would prompt resolves as a denial** — including a `permissions.ask` entry in
your own settings. A stage session that cannot run `git`, `gh` or an edit does
not fail loudly; it stalls and comes back not-`done`, which is what the retry
cap is there to catch.

The driver therefore passes an explicit profile, which you can override:

```
--permission-mode acceptEdits
--allowedTools Bash Edit Write Read Glob Grep Agent Skill TodoWrite AskUserQuestion WebFetch WebSearch NotebookEdit
```

`AskUserQuestion` is in that list even though an unattended session never asks
anything: the same profile is what you copy to launch a session by hand, and
without the tool a session falls back to asking in prose, which is worse in
every mode.

Three consequences worth knowing before the first unattended run:

- **Any `permissions.ask` entry a session needs is a hard stop — `gh pr merge`
  is just the one `merge: auto` guarantees to hit.** If your settings ask
  before a merge — as a branch-protection or merge-gate policy usually does —
  that ask is a denial headless, so every stage stalls at its own PR and the
  driver stops at the first one with nothing merged. But it is not only the
  merge: in the first end-to-end run, closeout was stopped cold by an `ask` on
  `rm -rf` when it tried to clear a build cache, a rule nobody had thought of
  as part of the plan. Go through your `ask` list with the plan's commands in
  mind before driving it. **An `ask` entry is close to unbeatable
  per-command.** Measured, each against a real user-level `ask` rule and a
  real tool call:

  | Attempt | Result |
  |---|---|
  | `--allowedTools Bash` | still denied |
  | `--permission-mode bypassPermissions` | still denied |
  | `--settings` with a matching `permissions.allow` | still denied |
  | `--setting-sources project,local` | **allowed** |

  Only the last works, and it works by never loading your user settings at all:

  ```bash
  python scripts/plan_driver.py --setting-sources project,local
  ```

  That is a blunt instrument, not a scalpel. Dropping `user` drops **everything**
  in it — your hooks (including any branch guard), your user `CLAUDE.md`, and the
  rest of your permission rules — for every stage session. If you will not drop
  `user`, be honest that the plan is then **semi-attended, not unattended**: set
  `merge: manual`, let the driver run each stage up to its PR and stop (the next
  bullet), merge it yourself, restart the driver. That costs you one click per
  stage; the alternative costs you every safety rule you have, per session.
- **`merge: manual` means no stage ever reaches `done` unattended.** Offering a
  merge is asking a person, and unattended mode never waits for an answer. The
  stage is not marked `blocked` for it — it ends at `doing` with its PR open,
  which is why the driver's retry cap is what eventually stops the run. The
  driver says so on startup when it reads `merge: manual`.
  A plan you intend to drive wants `merge: auto` on its plan-flags line.
- **`bypassPermissions` bypasses less than the name suggests.** Measured: a
  `PreToolUse` hook still runs headless and its `deny` is still honoured under
  it, and so is a `permissions.ask` entry. That cuts both ways — a hook-based
  branch guard keeps protecting you through an unattended run, and neither a
  hook nor an `ask` rule that refuses something a stage needs is escapable by
  changing permission mode. The only measured way past an `ask` is the
  `--setting-sources` route above, with the cost it carries.

### Driving an unreleased plugin — `--plugin-dir`

A stage session resolves `/plan-staged-rollout:plan-run` against the **installed**
plugin, not the working tree the driver was launched from. Testing an unreleased
change — to the plugin or to the driver itself — therefore needs the stage
sessions pointed at the tree under test:

```bash
python scripts/plan_driver.py --plugin-dir /path/to/plan-staged-rollout
```

The value is passed straight through to `claude --plugin-dir`, which loads a
plugin **for that session only** — no marketplace entry, no global install, and
nothing to undo afterwards. It is repeatable, and it takes a plugin directory or
a `.zip`. A directory has to contain `.claude-plugin/plugin.json` or the driver
refuses to start: silently falling back to the installed plugin would produce a
run that looks fine and tested the wrong code.

### Being told about it

The driver calls a notify command on every stop, on `blocked`, and on
finishing the plan. Set it with the `PLAN_DRIVER_NOTIFY` environment variable
(or `--notify`):

```bash
PLAN_DRIVER_NOTIFY='curl -s -d' python scripts/plan_driver.py
```

The message is appended as one argument, and `PLAN_DRIVER_EVENT`,
`PLAN_DRIVER_MESSAGE`, `PLAN_DRIVER_STAGE` and `PLAN_DRIVER_PLAN` are exported
into the command's environment, so both a one-liner and a script work without
a wrapper. **An environment variable rather than a `.plan/` setting**, because
`.plan/` is tracked and shared on the plan branch: a notify target is usually
a personal webhook or a machine-local notifier, and committing it would both
leak it and force everyone working the plan onto one channel.

### Deliberately out of scope

- **Parallel waves.** The driver is sequential. When more than one stage is
  runnable it says so and takes them in stage-index order; running a wave
  concurrently is still one terminal per stage, as above.
- **Relaying questions to you mid-flight.** A stage that needs an answer
  becomes `blocked` with a runbook and the driver notifies you. That is the
  whole mechanism — there is no live chat relay.

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

- Parallel waves in the unattended driver (it is sequential today)
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
  README.md                      ← you are here
  skills/staged-rollout/
    SKILL.md                     # method: principles, decomposition guidance,
                                 #   flag heuristics, anti-patterns
    references/templates/        # PLAN.md, LEDGER.md, stage-N.md, stage-f-review.md, README.md
  examples/
    uptime-page/.plan/           # worked example: a filled-in scaffold, mid-flight
  commands/
    plan-stages.md               # /plan-stages <idea>  — bootstrap .plan/
    plan-run.md                  # /plan-run <N>        — execute one stage
    plan-close.md                # /plan-close          — final PR + cleanup
  hooks/
    hooks.json                   # SessionStart registration
    run-hook.cmd                 # polyglot cmd/bash wrapper (Windows + Unix)
    session-start                # .plan/-aware nudge: next runnable stage
  scripts/
    plan_driver.py               # unattended driver: one claude -p per stage
```

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
