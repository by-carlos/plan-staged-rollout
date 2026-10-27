---
description: Turn a project idea into a committed staged-rollout `.plan/` scaffold. Use when the user says "bootstrap a plan for X" or "break this project into stages".
argument-hint: <project idea>
---

# /plan-stages — bootstrap a `.plan/` scaffold

Turn a project idea into a committed `.plan/` folder: requirements → triage →
decompose → scaffold → brief → review → commit. **No stage is executed here.**
This command is a thin wrapper around the `staged-rollout` skill; the skill and
its `references/` are the single source of truth for the method and file
formats. Do not restate the protocol here or in the scaffold — reference it.

Project idea: **$ARGUMENTS**

**Bootstrap has no `--unattended` mode, and that is deliberate.** Every other
command in this plugin honours one (see the `staged-rollout` skill, *Unattended
mode*); this one does not, because requirements, decomposition and frozen
decisions are design questions with no defensible defaults to declare in
advance, and a badly decomposed plan costs far more than the session it saved.
Where a plan must be bootstrapped headless anyway, a fully-specified brief that
says to make every decision and ask nothing works as an ordinary prompt — it
needs no contract behind it, and the weight gate below still applies.

First, load the method: invoke the **`staged-rollout`** skill (via the Skill
tool) and follow its decomposition guidance, flag heuristics, and git model.
The templates to copy live at
`${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/references/templates/`
(`PLAN.md`, `LEDGER.md`, `stage-N.md`, `stage-f-review.md`, `README.md`,
`RUNNER.md`, `BRIEF.md`). Two more references govern steps below:
`references/plan-review.md` (the lenses, digest and outcomes) and
`references/decisions-format.md` (*Where it lives* — which existing decision
record a plan adopts).

Then work through these steps **in order**. The user is asked things at three
points only — the playback (step 2), the one batch (step 3), and the review
ask with the brief (step 8) — plus the commit OK (step 9).

1. **Weight gate (first, before anything else).** Bootstrap is the
   highest-leverage session of a plan. Verify from your own system prompt that
   the session model is **Opus-class or better**, checked mechanically against
   the skill's **Model weight tiers** rubric — not the model's own guess about
   itself. State the effort recommendation (**medium or higher**) next to the
   effort actually set, read from `CLAUDE_EFFORT`; if that variable is absent,
   say it could not be read rather than assuming it matched. If
   the model is lighter than Opus-class, warn and **offer to abort** so the
   user can relaunch on a heavier model, before doing any design or
   scaffolding work. If the disclosed model doesn't recognizably match a tier
   in the rubric, don't guess — state the exact model ID/name and ask the
   user which tier applies.

2. **Requirements and playback — before any decision.** Capture what the user
   needs before deciding how to build it.

   **Size first.** A plan is for work of roughly four or more sessions — the
   line the skill's *When NOT to use it* already draws. Work that fits one
   issue is small: its acceptance criteria are the spec, it gets no brief and
   no plan review, and it belongs in `work-issue` or a single session. Say so
   and offer to stop rather than scaffolding it. There is no other size
   metric: within a plan, depth scales by what the plan touches (step 7's lens
   triggers), never by stage count. (The programme check in step 3 counts
   independent outcomes, not stages, and is not a size metric.)

   Then draw out the five requirement bullets of the `PLAN.md` template's
   `## Requirements` section from `$ARGUMENTS`, any issue it names, and what
   the repo shows: **Outcome** (in the user's words), **Day to day** (where
   they are, which device, what happens while they are away), **Constraints,
   ranked** (the first wins a conflict), **Out of scope**, and **Done, as
   checks** a script or a person can run. Read only what you need to fill
   them — this is not a design pass.

   **Existing decision record.** Check whether the repo already keeps one, as
   `decisions-format.md` › *Where it lives* defines: an ADR folder
   (`docs/adr/`, `doc/adr/`, `adr/`, or `docs/decisions/` holding numbered
   files) or an existing current-decisions document. Record what you find as a
   triage item for step 3 — **Decided** when there is exactly one clear
   target (or none, in which case the plan's lasting decisions will go to a
   new `DECISIONS.md` at close), **Needs you** when there are several
   candidates or it is unclear whether a document is a decisions list. Never
   plan a parallel list beside an existing one.

   **Play it back** to the user in plain language — a short paragraph per
   bullet, no protocol vocabulary — and wait for them to confirm or correct
   it. Corrections are folded in and the changed bullets played back again;
   nothing in step 3 starts until the requirements are confirmed. They become
   the scaffolded `PLAN.md`'s `## Requirements` section, unchanged.

3. **Decision triage — one batch ask.** List every decision the build needs
   before stage work can start, and sort each into the triage groups the
   `PLAN.md` template defines under *Frozen decisions*:
   - **Decided** — reversible and low impact: settle it yourself, with its
     reason. Not asked. Decisions `$ARGUMENTS` already settles land here too.
   - **Needs you** — taste, irreversible, cost, security, or anything
     external: put to the user. Each comes with the options you weighed and a
     recommended answer.
   - **Default for now** — a working default, flagged with when to revisit.

   **Programme check.** Count the outcomes in the confirmed requirements that
   could each merge into `main` on their own — a count of outcomes, never of
   stages, which are not known until step 4. Two or more: put a **Needs you**
   decision in the batch proposing a **programme** — one plan per outcome, in
   running order, each closing into `main` through its own final PR — with
   the outcomes listed and a recommended answer. Accepted: this bootstrap
   scaffolds the **first** plan only, its `## Requirements` narrowed to that
   outcome, and step 6 writes the programme index
   (`references/programme-format.md`). Declined, or fewer than two outcomes:
   one plan, nothing else changes. When `PROGRAMME.md` already exists on
   `main` and its first line names this plan, the programme is already
   accepted: scaffold that plan, propose nothing, and ask nothing.

   Then evaluate the plan-review lens triggers (`plan-review.md` › *The four
   lenses*) against the confirmed requirements, and add the resulting lens
   list to the batch: Simplicity always, each other lens with the trigger that
   turned it on. The user may add or drop lenses in their answer.

   **Ask once.** Every **Needs you** decision and the lens list go to the user
   in **one** batch — not one question at a time, and not a design pass that
   trickles questions out. Show the **Decided** and **Default for now** items
   alongside, one line each, so the user can promote any of them to a question
   in the same reply. A second ask is allowed only when an answer itself opens
   a new **Needs you** question; say so when it happens. A **Needs you**
   decision the user leaves unanswered stays *pending* and names the stages
   that wait on it (template wording `(Needs you — pending; blocks S<N>)`) —
   only those stages are blocked, and step 6 still scaffolds.

   Outcomes land **directly as Frozen decisions in the scaffolded `PLAN.md`**,
   each tagged with its group — never as a separate spec document (a second
   source of truth is exactly what this method exists to prevent).

4. **Decompose.** Apply the skill's guidance: smallest sensible stages, explicit
   `depends`, the keystone as **S0**, deliberately cheap process flags
   (`direct`, `inline` — escalate only where a stage genuinely warrants it),
   and a `model`/`effort` sized to finish the stage rather than minimised.
   Then **append the standing `SF: plan review` stage** as the
   last row (it catalogs loose ends and never implements), scaffolded from
   `stage-f-review.md` — not a copy of `stage-N.md` — since it already bakes
   in the three-outcome checklist and acceptance check.

   **A wait measured in days is not a stage.** A soak period, a quarter-end,
   a vendor's reply — anything the plan would sit idle on for days — is
   refused as a stage: a stage that waits holds a session, a branch and a
   worktree open for nothing. Leave it out of the stage index and record it
   as a **dated follow-up** under `PLAN.md` › Requirements › Out of scope: the
   date, the exact check, the pass condition (with why that threshold, per the
   `stage-N.md` acceptance wording) and what to do if it fails. SF lists it and
   files it after the user's yes. A wait of hours stays inside the stage that
   needs it.

   **Number stages in running order.** Stage IDs are plain numbers plus `SF`.
   Number the stages in the order they will run: stages that can run side by
   side get consecutive numbers, and no stage has a lower number than anything
   it `depends` on. **Reject a suffixed ID** (`S12b`) — renumber instead of
   suffixing. Existing suffixed IDs in a plan already in flight are still
   read, but never created here.

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
   acceptance needs a person's eyes or hands; `live` for a stage that deploys
   or changes a running system (a driver never fires it, and two `live`
   stages never run at once — where two would land in the same wave, add the
   edge between them); `local` for a stage you already
   know needs a resource only the local machine has — local hardware, a
   LAN-only host, a secret not committed anywhere reachable, or a
   locally-installed toolchain; `auto` for everything else — it is the
   default, and neither `human` nor `local` changes anything until a plan is
   actually run unattended. Then apply the skill's **group by gate** rule to
   the graph: `human` stages go at the **front** (where frozen decisions get
   settled or amended), `live` stages at the front or the **end**, and the
   review stage last, with the mechanical `auto` stages in between — never a
   `human` or `live` stage wedged between two `auto` ones unless a dependency
   edge genuinely forces it. `local`
   stages carry no design question, so they need no such front-loading — they
   sit wherever the dependency graph puts them. When the human-grouping rule
   and the graph disagree, the graph wins and you say so.

   **A pending decision is a `depends` fact too.** Every stage a pending
   **Needs you** decision names must be one that genuinely consumes it — the
   same naming rule as for edges above.

5. **Git model (fixed, not a question).** Record the frozen git protocol in
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
   `$ARGUMENTS` or the requirements say the plan doubles as the project's
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

6. **Scaffold — dispatch a subagent, don't commit yet.** By this point the
   requirements, the decisions, the stage index, the git model, and the
   worktree model are all settled; nothing left in this step is a decision,
   so don't keep the templates resident to do it. The scaffold stays
   **uncommitted** until the review in step 8 has been applied.

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
   - the confirmed requirements from step 2, for `PLAN.md`'s
     `## Requirements`;
   - the frozen decisions from step 3, each with its triage group (and, for a
     pending **Needs you**, the stages it blocks);
   - the completed stage index from step 4, including the standing `SF: plan
     review` row and every stage's `gate`;
   - the frozen git model and worktree model from step 5, and the complete
     plan flags line it decided (both `merge` and `plan-dir`);
   - the plugin version from `.claude-plugin/plugin.json`, for `RUNNER.md`'s
     scaffold marker.

   **Before dispatching, copy the templates yourself**, as a plain copy with
   nothing else in the command: `mkdir -p <repo>/.plan && cp
   "${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/references/templates/"*.md
   <repo>/.plan/`, then `cp
   "${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/references/decisions-format.md"
   <repo>/.plan/` — the final review stage reads `.plan/decisions-format.md`
   first, and a cloud session has no plugin to fall back on. Give the subagent **only `<repo>/.plan/`** — never the
   plugin's templates path — and tell it to edit those working copies with
   the Edit and Write tools, no shell text substitution. The plugin cache
   sits under the Claude config directory, outside the repo: a shell command
   that names it and also edits files (`sed -i` on a variable path) raises a
   permission prompt that reads as an edit to the plugin itself, even when
   only the copies are touched.

   Instruct it to fill every placeholder in `<repo>/.plan/`, using the
   copies there as its templates — **except `BRIEF.md` and `PLAN.md` ›
   Plan review, which it leaves untouched** (steps 7 and 8 own them):
   `stage-N.md` **once per stage**, each
   written as `stage-<N>-<slug>.md`, then the `.plan/stage-N.md` copy
   removed; and `stage-f-review.md` **once**, filled in place under the same
   name (no slug — it's the standing final stage; state this explicitly
   rather than trusting it to infer from the template name). Every stage
   file's `## Artifacts` lists the paths the stage writes — step 7 reads them
   for lens triggers, and the close-time decision triage reads them for paths.
   `RUNNER.md` is kept **whole with its placeholders filled and its header
   comment's `<version>` set** — it is the stage-runner contract the plan
   carries so any session, cloud included, can run a stage from the one-line
   instruction "run stage \<N> of plan branch \<branch>; first run `git fetch
   origin <branch> && git checkout -B <branch> origin/<branch>`, then follow
   `.plan/RUNNER.md`" (the checkout is in the instruction because a cloud
   clone starts on the default branch, where `RUNNER.md` does not exist);
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
   files written** — nothing else. **The subagent runs no git command.**

   **Programme index — only when a programme was accepted in step 3.** After
   the subagent returns, write `PROGRAMME.md` at the **repository root**
   yourself, not into `.plan/` and not through the subagent: follow
   `references/programme-format.md`, one numbered line per plan in running
   order, each with the outcome in plain words and the plan branch
   `plan-<slug>` as its pointer, the first line being this plan. Leave it
   uncommitted with the rest of the scaffold. Skip this when the programme
   already exists on `main` (this plan is a later one, and its line is
   already there) or when no programme was accepted.

7. **Brief.** Generate `.plan/BRIEF.md` from the filled `PLAN.md`, following
   the generation rules in the `BRIEF.md` copy's header comment (and dropping
   that comment): line 1 is the stamp
   `Generated from PLAN.md @ <hash> — do not edit`, `<hash>` being the first
   12 hex characters of `git hash-object .plan/PLAN.md`; every section names
   the `PLAN.md` section it came from; nothing appears in the brief that
   `PLAN.md` does not hold. The brief is always this file, tracked with the
   rest of the scaffold. **Where the Artifact tool exists**, also publish the
   same content as an artifact — the file is the brief, the artifact only
   renders it; with no Artifact tool (cloud, terminal, phone) the file alone
   is the brief, and nothing else changes.

   **Re-check the lens triggers** against every stage file's `## Artifacts`
   now that they exist. A lens that only turns on here is added — not asked
   about — and shown with its trigger in the brief's lens line. At most four
   lenses run.

   **Regenerate the brief after every later `PLAN.md` edit** — review
   outcomes in step 8, the user's feedback on the brief, anything else — and
   republish the artifact to the same URL. Feedback, in chat or as artifact
   comments, is applied to `PLAN.md` only, never to `BRIEF.md`: a hand edit
   to the brief is overwritten at the next regeneration, by design.

8. **Plan review — before the commit.** Run the lenses on the uncommitted
   scaffold exactly as `plan-review.md` › *Running a lens* defines: one
   subagent per lens, in parallel, each on its table model (Sonnet for
   Simplicity and Operator; this session's own model for Architect and
   Security), each writing its findings to its own scratchpad file. Then one
   Sonnet subagent merges them into the digest that `plan-review.md` ›
   *The digest* defines (finding rule applied, duplicates folded, at most
   ~40 lines) and writes it to the scratchpad. **This session reads the
   digest only, never the lens files.**

   Give every digest finding one of the three outcomes (`plan-review.md` ›
   *Three outcomes*). Apply the ones the frozen decisions already settle
   without asking — edit `PLAN.md` or the stage file the finding points at.
   Findings that would change a **Needs you** decision, or that turn on
   taste, cost or something external, go to the user in **one** ask, each
   with a recommended outcome — together with the brief (the artifact link,
   or the `.plan/BRIEF.md` path where there is none) and an invitation to
   give feedback on it. Apply the answers and the feedback to `PLAN.md`,
   write the record into `PLAN.md` › Plan review (date, lenses with their
   triggers, one line per digest finding with its outcome), and regenerate
   the brief (step 7). A finding that reaches the digest is never silently
   dropped.

9. **Commit.** Every git write stays here in the parent: **propose creating
   the plan branch `plan-<slug>` off `main`** and put the scaffold there —
   `.plan/` lives on the plan branch and is **tracked** there, `BRIEF.md`
   included. **Propose the scaffold commit** (conventional message, e.g.
   `chore(plan): scaffold .plan/ for <slug>`) and wait for the user's OK — do
   not create the branch or commit unilaterally. `PROGRAMME.md`, when step 6
   wrote it, goes in the same commit. Once committed, **push the
   plan branch with an upstream** (`git push -u origin plan-<slug>`) — no
   approval needed for a feature branch. A local-only plan branch makes every
   later preflight's fetch and fast-forward a silent no-op. Then confirm the
   scaffold is really tracked: `git ls-files .plan/` must list the files the
   manifest said were written, plus `BRIEF.md`.

10. **Run record.** Append one effort-log row for the bootstrap, so the
    planning overhead can be read off the log after a real plan:

    ```
    python "${CLAUDE_PLUGIN_ROOT}/skills/staged-rollout/scripts/effortlog.py" log \
      --source plan-stages --repo <owner/repo> --target <plan-slug> \
      --estimated-tier <this session's model/effort> \
      --outcome <plan-scaffolded|abandoned> \
      --note "<one line: stages, lenses run, findings changed/followed-up/accepted>"
    ```

    The script totals this session's subagents itself — the scaffold
    subagent, every lens and the digest merge — into the row's
    `subagent_tokens`, so do not add them up by hand. Run it on an abandoned
    bootstrap too: a plan stopped at the size check or the playback is part
    of what planning costs. Writing is **opt-in** — with `CLAUDE_EFFORT_LOG`
    unset the script writes nothing and exits 0. A failure here is reported in
    one line and never blocks the bootstrap.

11. **End announcement.** State explicitly that **bootstrap is finished and no
    stage was executed**, and where the brief is (the artifact link, and
    `.plan/BRIEF.md` on the plan branch). Then print the **wave structure and
    critical path**, derived from the `Depends` column — never stored as a
    column of its own, since waves are a view of the graph and a stored copy
    is what drifts. Wave 0 is every stage with no `depends`; wave *k* is every
    stage whose deepest prerequisite sits in wave *k−1*. Show it compactly:

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
    knows where concurrency is available.

    Then hand off **wave 0** — the stages that can run now — exactly as
    `/stage-run`'s end announcement hands off a runnable set: for each one,
    the fresh-session prompt **"run stage \<N> of the plan"** or the explicit
    command **`/plan-staged-rollout:stage-run <N>`**, with its recommended
    `model`, `effort` and `gate` from the stage index; and, in the desktop
    app, one card per stage by following `commands/stage-run.md` step 7,
    *Desktop-app chips*, as written — `spawn_task` or `start_session`,
    whichever this session has, under the same conditions and with the same
    fields. Read that bullet's "what the finished stage left behind" as "what
    the bootstrap left behind". The printed command stays the handoff on every
    surface that shows no card. If step 6 found a modal-model majority, repeat
    that recommendation here too (e.g. *"consider `/model opus` as your
    session default — it covers 6 of 8 stages"*). Repeat the plan flags line.
    When a programme was accepted, also say that this scaffolds the first plan
    only and name the remaining plans from `PROGRAMME.md`; each is bootstrapped
    from `main` after the one before it has closed. Then stop.
