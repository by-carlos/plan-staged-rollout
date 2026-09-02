---
description: Bootstrap a staged-rollout .plan/ from a project idea — design, decompose, scaffold, and commit. Executes no stage.
argument-hint: <project idea>
---

# /plan-stages — bootstrap a `.plan/` scaffold

Turn a project idea into a committed `.plan/` folder: design → decompose →
scaffold → commit. **No stage is executed here.** This command is a thin
wrapper around the `staged-rollout` skill; the skill and its
`references/templates/` are the single source of truth for the method and file
formats. Do not restate the protocol here or in the scaffold — reference it.

Project idea: **$ARGUMENTS**

**Bootstrap has no `--unattended` mode, and that is deliberate.** Every other
command in this plugin honours one (see the `staged-rollout` skill, *Unattended
mode*); this one does not, because decomposition and frozen decisions are
design questions with no defensible defaults to declare in advance, and a badly
decomposed plan costs far more than the session it saved. Where a plan must be
bootstrapped headless anyway, a fully-specified brief that says to make every
decision and ask nothing works as an ordinary prompt — it needs no contract
behind it, and the weight gate below still applies.

First, load the method: invoke the **`staged-rollout`** skill (via the Skill
tool) and follow its decomposition guidance, flag heuristics, and git model.
The templates to copy live at
`${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/references/templates/`
(`PLAN.md`, `LEDGER.md`, `stage-N.md`, `stage-f-review.md`, `README.md`,
`RUNNER.md`).

Then work through these steps **in order**:

1. **Weight gate (first, before anything else).** Bootstrap is the
   highest-leverage session of a plan. Verify from your own system prompt that
   the session model is **Opus-class or better**, checked mechanically against
   the skill's **Model weight tiers** rubric — not the model's own guess about
   itself. State the effort recommendation (**medium or higher**) as a
   reminder — effort is not introspectable, so never claim to verify it. If
   the model is lighter than Opus-class, warn and **offer to abort** so the
   user can relaunch on a heavier model, before doing any design or
   scaffolding work. If the disclosed model doesn't recognizably match a tier
   in the rubric, don't guess — state the exact model ID/name and ask the
   user which tier applies.

2. **Design pass (only if the design isn't already settled).** If `$ARGUMENTS`
   already carries settled decisions, skip straight to decomposition. Otherwise
   run a design pass: use **`superpowers:brainstorming`** when it is installed;
   else fall back to a built-in lightweight flow — **one question at a time,
   multiple-choice preferred**, converging on the decisions worth freezing.
   Outcomes land **directly as Frozen decisions in the scaffolded `PLAN.md`** —
   never as a separate spec document (a second source of truth is exactly what
   this method exists to prevent).

3. **Decompose.** Apply the skill's guidance: smallest sensible stages, explicit
   `depends`, the keystone as **S0**, and deliberately cheap flags (`direct`,
   `inline`, the cheaper capable model — escalate only where a stage genuinely
   warrants it). Then **append the standing `SF: plan review` stage** as the
   last row (it catalogs loose ends and never implements), scaffolded from
   `stage-f-review.md` — not a copy of `stage-N.md` — since it already bakes
   in the three-outcome checklist and acceptance check.

   **Do not serialise `depends` out of habit.** `depends` means "cannot safely
   start until", not "I wrote this stage after that one". Writing the chain
   `S0 → S1 → S2 → S3` where the real graph is `S0 → {S1, S2, S3}` is the most
   common decomposition error here: it reads as correct in the index and
   silently forces three rounds of work where two would do. For every edge you
   write, name the artifact the dependent stage actually consumes. If you
   cannot name one, drop the edge.

   **Then check the other direction — shared write territory.** Two stages
   with no logical dependency can still write the same files, which makes them
   unsafe to run at the same time even though the graph says they are
   independent. `depends` is the only place that can express this; there is
   deliberately no separate territory field, because a second record of one
   constraint is a second thing to drift. So where two stages that would land
   in the same wave write the same file, add the edge. A small, genuinely
   order-independent overlap may be left in one wave on purpose — say so
   explicitly rather than leaving it implicit.

   **Then set `gate` per stage, and group by it.** `gate` says whether a
   stage may be launched with nobody watching (the skill's *Flag heuristics*
   define it; the remote orchestrator reads it before firing a stage).
   Decide it here, from the decomposition, never by asking the user row by
   row:
   `human` for every `mode: brainstorm` stage and for any stage whose
   acceptance needs a person's eyes or hands; `local` for a stage you already
   know needs a resource only the local machine has — local hardware, a
   LAN-only host, a secret not committed anywhere reachable, or a
   locally-installed toolchain; `auto` for everything else — it is the
   default, and neither `human` nor `local` changes anything until a plan is
   actually run unattended. Then apply the skill's **group by gate** rule to
   the graph: `human` stages go at the **front** (where frozen decisions get
   settled or amended) and the review stage at the **end**, with the
   mechanical `auto` stages in between — never a `human` stage wedged between
   two `auto` ones unless a dependency edge genuinely forces it. `local`
   stages carry no design question, so they need no such front-loading — they
   sit wherever the dependency graph puts them. When the human-grouping rule
   and the graph disagree, the graph wins and you say so.

4. **Git model (fixed, not a question).** Record the frozen git protocol in
   `PLAN.md`: **branch-per-stage** — `main` → `plan-<slug>` (the plan branch)
   → one `plan-<slug>-s<N>` branch and PR per stage, no exceptions, final PR
   to `main` at closeout. It is the only supported model — do not ask the
   user to choose. Seven frozen semantics — six here, the seventh (worktree-per-stage)
   just below: (1) one branch per stage, cut from
   the plan branch; (2) commits are compulsory and incremental — commit at
   logical units as the stage progresses, not once at the end; (3) a stage PR
   into the plan branch is compulsory — the finish protocol creates it, it is
   not offered; (4) a stage cannot be marked `done` until its PR is merged
   into the plan branch; (5) after the merge, return to the clone (already on
   the plan branch) and fast-forward before the session ends; (6) merge type
   is fixed by position —
   stage PRs are **squash-merged** into the plan branch (merged branch
   deleted), and the final PR from the plan branch into `main` is a **normal
   (non-squash) merge** so each stage keeps its own commit on `main`. Do
   **not** create any *stage* branch
   here — stage branches (`plan-<slug>-s<N>`) are proposed and created at
   stage time by `/plan-staged-rollout:stage-run`, never at bootstrap.

   **The plan-level `merge` flag — written, not asked.** Write
   **`merge: auto`** on the plan flags line under the stage index without
   asking: a step that finishes itself squash-merging its own stage PR once
   checks are green (stage PRs only — the plan→main PR is manual in every
   mode, and nothing here may change that) is what unattended and
   cloud-driven runs need, so it is what a new plan gets by default. Repeat
   the value in the end announcement. `merge: manual` — offer each stage
   PR's merge for the user's OK instead — remains a value a plan author can
   set explicitly by editing `PLAN.md`'s plan flags line, for anyone who
   wants per-merge control while driving a plan locally; `/stage-run`'s
   finish protocol still honours it exactly as before. Either way the user
   can flip the flag later in `PLAN.md` in one line.

   **The `plan-dir` flag — written, not asked.** The same line also carries
   `plan-dir: delete` \| `keep`, the plan's declared answer to closeout's
   "delete `.plan/` or keep it?" question. Write **`plan-dir: delete`** unless
   `$ARGUMENTS` or the design pass says the plan doubles as the project's
   documentation, in which case write `keep`. Don't ask: `delete` is what
   `/plan-close` already recommends, an interactive closeout still puts the
   choice to the user with this value as its recommendation, and one more
   bootstrap question buys nothing. So the finished line reads
   ``Plan flags: `merge: auto` · `plan-dir: delete``` (with whichever values
   this plan chose).

   **Worktree model (also fixed, also not a question).** Record it alongside
   the git model: the clone is parked on `plan-<slug>` for the life of the
   plan, and every stage branch is checked out only in its own sibling
   worktree `../<repo-dirname>-s<N>`, provisioned at stage time and torn down
   after its PR merges. It is what makes a fanned-out wave physically
   runnable rather than merely safe on paper. As with stage branches, create
   **no** worktree here — bootstrap leaves the clone on the plan branch and
   nothing else.

5. **Scaffold — dispatch a subagent, then commit.** By this point the design,
   the stage index, the git model, and the worktree model are all frozen;
   nothing left in this step is a decision, so don't keep the templates
   resident to do it.

   First, **check that `.plan/` is not ignored — yourself, before dispatching
   anything**: `git check-ignore -v .plan/PLAN.md`. If a rule matches, **stop
   and report it**; do not scaffold into an ignored path. An untracked
   `.plan/` deadlocks the plan: decision-only stages produce no commit and
   therefore no PR, which makes their dependents' gates unsatisfiable, and the
   whole decision record is lost with the working directory. Removing the
   ignore rule is the fix, and it is the user's call — this check cannot leave
   the session.

   Then dispatch a `sonnet` subagent (not a cheaper tier: the final review
   stage must be scaffolded from `stage-f-review.md`, **never** from a copy of
   `stage-N.md`, because that template already bakes in the three-outcome
   checklist and its acceptance check — a cheaper tier copying the obvious
   template produces a scaffold that looks right, commits clean, and fails
   only much later when the review stage runs and its checklist is missing)
   carrying:
   - the frozen decisions from step 2;
   - the completed stage index from step 3, including the standing `SF: plan
     review` row and every stage's `gate`;
   - the frozen git model and worktree model from step 4, and the complete
     plan flags line it decided (both `merge` and `plan-dir`);
   - the path to `skills/staged-rollout/references/templates/`
     (`PLAN.md`, `LEDGER.md`, `README.md`, `RUNNER.md`, `stage-N.md`,
     `stage-f-review.md`);
   - the plugin version from `.claude-plugin/plugin.json`, for `RUNNER.md`'s
     scaffold marker.

   Instruct it to copy the templates into `<repo>/.plan/` and fill every
   placeholder: `stage-N.md` **once per stage**, each renamed to
   `stage-<N>-<slug>.md`, and `stage-f-review.md` **once**, renamed to
   `stage-f-review.md` (no slug — it's the standing final stage; state this
   explicitly rather than trusting it to infer from the template name).
   `RUNNER.md` is copied **whole with its placeholders filled and its header
   comment's `<version>` set** — it is the stage-runner contract the plan
   carries so any session, cloud included, can run a stage from the one-line
   instruction "run stage \<N> of plan branch \<branch> per `.plan/RUNNER.md`";
   it is a deliberate generation-time copy (the header says how it refreshes),
   never a reference to plugin files that a cloud run cannot see. After
   the stage index is filled, compute the **modal `model`** across all stage
   rows (including SF); if one model is recommended by a strict majority, note
   it in `.plan/README.md`'s "How to run a stage" section as a one-line hint
   (e.g. *"6 of 8 stages recommend `opus` — setting it as your session default
   means the weight gate only prompts on the exceptions."*) — a
   bootstrap-time convenience only, it never changes the per-stage
   `model`/`effort` values, which stay authoritative and are still checked
   individually by `/stage-run`'s weight gate. Skip the hint if there's no
   strict majority (e.g. an even split). The subagent returns a **manifest of
   files written** — nothing else.

   **The subagent runs no git command.** Every write stays here in the
   parent: **propose creating the plan branch `plan-<slug>` off `main`** and
   put the scaffold there — `.plan/` lives on the plan branch and is
   **tracked** there. **Propose the scaffold commit** (conventional message,
   e.g. `chore(plan): scaffold .plan/ for <slug>`) and wait for the user's
   OK — do not create the branch or commit unilaterally. Once committed,
   **push the plan branch with an upstream** (`git push -u origin
   plan-<slug>`) — no approval needed for a feature branch. A local-only plan
   branch makes every later preflight's fetch and fast-forward a silent
   no-op. Then confirm the scaffold is really tracked: `git ls-files .plan/`
   must list the files the manifest said were written.

6. **End announcement.** State explicitly that **bootstrap is finished and no
   stage was executed.** Tell the user their next action, in a **fresh
   session**, is **"run stage 0 of the plan"** — or the explicit command
   **`/plan-staged-rollout:stage-run 0`** — and state **S0's recommended model
   and effort** from the stage index. If step 5 found a modal-model majority,
   repeat that recommendation here too (e.g. *"consider `/model opus` as your
   session default — it covers 6 of 8 stages"*).

   Then print the **wave structure and critical path**, derived from the
   `Depends` column — never stored as a column of its own, since waves are a
   view of the graph and a stored copy is what drifts. Wave 0 is every stage
   with no `depends`; wave *k* is every stage whose deepest prerequisite sits
   in wave *k−1*. Show it compactly:

   ```
   wave 0: S0
   wave 1: S1, S2, S3     ← independent; one session each, concurrently
   wave 2: S4
   wave 3: SF
   critical path: S0 → S1 → S4 → SF (4 stages)
   ```

   State the two facts that follow: the wave count is the fewest rounds this
   plan can take, and the critical path is the floor on elapsed time that no
   amount of parallelism removes. Name which waves fan out so the operator
   knows where concurrency is available — but do **not** offer to launch those
   sessions, because a session cannot start independent top-level sessions.
   Then stop.
