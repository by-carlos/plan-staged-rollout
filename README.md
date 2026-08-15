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
5. **A branch per stage.** Each stage lands as its own PR into the plan
   branch. Reviewing is small, undoing is a branch delete, and one stage's
   "quick fix" can never contaminate another's history.

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
- asks your git strategy (default: branch-per-stage, below);
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
3. **Dependency gate.** If a prerequisite isn't `done` in the ledger, stop.
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
   finished and name the next runnable stage — exact command plus its
   recommended model/effort; stop.

**Subtasks and interruption.** Stage steps are checkboxes. If a session must
stop mid-stage (blocked, context getting long, you interrupt), it marks the
stage `doing`, ticks the completed boxes, and writes a handoff note.
Re-running `/plan-staged-rollout:plan-run <N>` (or asking to "run stage \<N>
of the plan" again) resumes from the unticked boxes.

**Statuses:** `todo → doing → done`, plus `blocked` (waiting on a human or an
external gate — the stage becomes a runbook with exact steps for you) and
`skipped` (decided against, one-line reason recorded). Partial completion is a
normal, resumable state, not a failure.

### Session-start nudge

The real friction of a multi-day rollout isn't typing a long command — it's
that a fresh session doesn't know a rollout exists. A `SessionStart` hook
closes that gap: when the repo has a `.plan/` directory, every new session
starts already knowing the next runnable stage — a `doing` stage to resume,
else the first `todo` whose `depends` are all `done` — plus its recommended
model/effort from the stage index, and offers the exact `/plan-run` command.

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

### 3. Git model (default)

```
main
 └── plan-<slug>                    ← plan branch; .plan/ lives here
      ├── plan-<slug>-s0  → PR → plan-<slug>
      ├── plan-<slug>-s1  → PR → plan-<slug>
      └── ...
plan-<slug> → final PR → main       ← at /plan-close
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
  `main`. A stage cannot be marked `done` until its PR is merged.
- Merge type is fixed by position: stage PRs into the plan branch are
  **squash-merged** (one commit per stage, merged branch deleted); the final PR
  from the plan branch into `main` is a **normal (non-squash) merge**, so each
  stage lands on `main` as its own distinct commit.
- **Repo settings prerequisite:** the GitHub repo must allow both squash
  merging and merge commits. Recommended defaults: squash message = "Pull
  request title and commit details"; merge-commit message = "Pull request
  title and description" (so the distilled final-PR body lands in the merge
  commit on `main`).
- Branch-per-stage is the only supported model — it is recorded as a frozen
  decision at bootstrap, not a choice offered at that time.

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
stages the review spawned). Then it:

1. distills `PLAN.md` + the ledger into the final PR body, so the *why* and
   the as-built story survive on `main`;
2. deletes `.plan/` as the last commit on the plan branch (nothing is lost —
   the full plan history remains in git; keeping `.plan/` is an option for
   projects where the plan doubles as documentation);
3. proposes the PR from `plan-<slug>` to `main`. You review and merge.

---

## Per-stage knobs

Each stage declares its own weight, so you don't pay heavy process on trivial
work — and don't skimp on the hard parts:

| Flag | Values | Meaning |
|---|---|---|
| `depends` | stage id(s) or `—` | prerequisites that must be `done` first |
| `mode` | `direct` \| `brainstorm` | whether the stage needs a design pass first |
| `exec` | `inline` \| `subagent(<model>)` | where the implementation churn lives |
| `model` / `effort` | launch hints | recommended session weight; checked, not faked |

Defaults are deliberately cheap: `direct`, `inline`, the cheaper capable
model. Escalate only where a stage has genuine open design questions
(`brainstorm`) or heavy iteration churn (`subagent`).

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

- Subagent fan-out for independent sub-steps within a stage
- Parallel execution of independent stages
- Progress dashboard rendered from the ledger
- Skill evals (triggering accuracy, protocol adherence)

## Status

**Shipped** (v0.1.0). This README is the method document; the skill, the three
commands, and the templates are implemented. They were built with the method
itself — decomposed into a `.plan/` and executed stage by stage in this repo
(the plan folder was removed at closeout, as the method prescribes; its full
history is in git).

Layout:

```
plan-staged-rollout/
  .claude-plugin/plugin.json
  README.md                      ← you are here
  skills/staged-rollout/
    SKILL.md                     # method: principles, decomposition guidance,
                                 #   flag heuristics, anti-patterns
    references/templates/        # PLAN.md, LEDGER.md, stage-N.md, README.md
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
```
