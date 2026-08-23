# Changelog

All notable changes to the `plan-staged-rollout` plugin are documented here. The
format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
plugin follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries before 0.4.0 were made while this repository was the `carlos-plugins`
marketplace and therefore also cover the standalone skills that have since moved
elsewhere. See 0.4.0 for the split.

## [Unreleased]

### Added

- **The protocol now says where a stage session commits its own `blocked` row**
  (#98). It had always said to record the block and stop, never on which branch,
  and under worktree-per-stage that gap made the record invisible: a mid-stage
  block landed on the stage branch, so the driver re-read `doing` from the plan
  branch, relaunched a stage that had deliberately stopped, burned its retry cap,
  and only then wrote its own generic runbook — while the session's specific one
  sat unread on an unmerged branch. The rule is now stated once, in the template
  `PLAN.md`'s operating protocol under **Recording a block**, and referenced (not
  restated) from the skill, `/plan-run`, `LEDGER.md`, the README and the worked
  example. It turns on one thing: whether the stage branch exists yet. Before it
  does — the weight check, the `gate: human` backstop, a refused redo — the
  `blocked` row and runbook are committed straight onto the plan branch. After it
  does, they go on the stage branch and ride its PR, and the block is announced
  on the plan branch through a `### S<N>` section in `.plan/BLOCKED.md`, the
  sibling file from #89 that no stage branch ever edits. A stage that merely
  stopped at a withheld merge is explicitly **not** a block.

- **Preflight and the session-start hook read `.plan/BLOCKED.md`** (#98). A
  mid-stage block leaves the plan branch's ledger row reading `doing`, so the row
  alone cannot show it. Preflight step 0.5 now reports any `### S<N>` section
  alongside its ledger reconciliation, and the hook tells a fresh session to read
  the file before offering a stage as an ordinary resume. Neither deletes a
  section — that stays the operator's deliberate act.

- **One unattended mode, honoured at every decision point** (#86). `--unattended`
  is now a single contract across the whole plan lifecycle rather than a property
  of `/plan-run` alone. Every question the protocol can put to a person is
  classified once — it either has a **declared default** written on `PLAN.md`'s
  plan flags line, or it is a **hard stop** — and `--unattended` is the switch
  that selects default-over-ask. Interactive sessions keep asking exactly as
  before, and the skills are not forked into two bodies. The classification table
  lives in the `staged-rollout` skill, *Unattended mode*.

- **`/plan-close --unattended`** (#86). Closeout had no unattended behaviour at
  all: headless it asked prose questions that each ended the session, which cost
  four relaunches to reach the plan→main PR in the #85 validation run. It now
  applies the plan flags, clears finished stage worktrees, opens the plan→main PR
  and stops. **It still never merges that PR** — that gate survives every mode and
  has no flag.

- **`plan-dir: delete | keep` on the plan flags line** (#86). The plan's declared
  answer to closeout's "delete `.plan/` or keep it?" question. `delete` is the
  default and is what `/plan-close` already recommended, so an absent flag is
  today's behaviour; bootstrap writes it without asking, and an interactive
  closeout still puts the choice to you with this value as its recommendation.

- **The driver closes the plan out itself** (#86). Once every stage is `done` or
  `skipped`, `scripts/plan_driver.py` launches
  `/plan-staged-rollout:plan-close --unattended` as one more session instead of
  telling the operator to. A rollout now runs from bootstrapped `.plan/` to an
  open plan→main PR with exactly two human gates: a `gate: human` stage, and the
  final merge. New flags: `--no-close` (stop at "plan complete" as before) and
  `--close-model` / `--close-effort`, since closeout has no stage-index row to
  read a weight from. The outcome is confirmed with `gh pr list` and reported
  three ways — PR URL, no PR (closeout stopped at a gate, exit 1), or `gh` unable
  to answer.

- **`AskUserQuestion` in the driver's default `--allowedTools`** (#86). Not
  because an unattended session asks anything, but because the same profile is
  what an operator copies to launch a session by hand — without the tool, that
  session falls back to asking in prose.

- **`--plugin-dir` on `scripts/plan_driver.py`** (#85). Passes `claude
  --plugin-dir` through to every stage session, so a rollout can be driven
  against a plugin directory or `.zip` instead of the installed plugin.
  Repeatable. It exists because a stage session resolves
  `/plan-staged-rollout:plan-run` against the **installed** plugin regardless of
  where the driver was launched from — so before this flag there was no way to
  exercise an unreleased change to the plugin, or to the driver itself, without
  releasing it first. A directory that has no `.claude-plugin/plugin.json` is
  refused at startup rather than passed on, because the failure it prevents is
  a run that silently uses the installed plugin and looks like it passed. The
  side-loaded path is printed on the driver's own stream before the first
  launch.

- **`--setting-sources` on `scripts/plan_driver.py`** (#85). Passes
  `claude --setting-sources` through to every stage session. A `permissions.ask`
  entry in your own settings resolves as a denial in a headless session, which
  stalls `merge: auto` at the first stage PR; measured against a real `ask` rule,
  neither `--allowedTools`, nor `--permission-mode bypassPermissions`, nor a
  matching `permissions.allow` supplied via `--settings` gets past it. Omitting
  `user` from the setting sources does, because the rule is then never loaded —
  along with your user hooks and user `CLAUDE.md`, which is why the driver logs a
  warning when `user` is absent and the README recommends `merge: manual` over
  reaching for it.

- **`scripts/plan_driver.py` — an unattended stage driver** (#82). Runs a plan
  without a person at the keyboard: a re-scanning loop that reads
  `.plan/LEDGER.md` and `.plan/PLAN.md`'s stage index, recomputes the runnable
  set exactly as `/plan-run` does, launches the next stage as its own
  `claude -p "/plan-staged-rollout:plan-run <N> --unattended"` session at the
  stage's `model`/`effort`, waits, re-reads the ledger, and repeats. The ledger
  is the only state, so the driver can be stopped and restarted at any point.
  It stops — and calls a notify command — in front of a `gate: human` stage, on
  a stage that comes back `blocked`, when nothing is runnable, and when the
  plan is complete. `--dry-run` prints the whole order, with the model, effort
  and exact command per stage, launching nothing. Guardrails: it refuses to run
  on a protected branch (`main`, `master`, `release`, `trunk`, `develop`, or
  the remote default) with no override; a stage that fails to reach `done`
  within `--max-attempts` (default 2) is recorded as `blocked` with a runbook,
  committed, and never retried; model and effort are printed before every
  launch, with an optional `--max-budget-usd` ceiling passed through to each
  session. It never merges anything itself — stage PRs are merged by their own
  sessions under the plan's `merge` flag, and the plan→main PR stays manual in
  every mode. Notify is configured through the `PLAN_DRIVER_NOTIFY`
  environment variable rather than a `.plan/` setting, because `.plan/` is
  tracked and shared on the plan branch while a notify target is personal and
  machine-local. Sequential only; parallel waves and any live relay of
  in-flight questions are deliberately out of scope. README gains an
  **Unattended runs** section documenting the `--permission-mode` /
  `--allowedTools` profile a `-p` session needs, that a `permissions.ask` entry
  acts as a denial headless (so `merge: auto` is incompatible with a merge-gate
  policy), and that `merge: manual` means no stage reaches `done` unattended.

- **`merge: auto|manual` plan flag and `gate: auto|human` stage flag** — the
  contract an unattended runner needs, without the runner itself (#81; the
  runner is separate work under #80). `gate` is a new last column of the
  `PLAN.md` stage index: `human` marks a stage that must never be launched
  with nobody watching. `merge` lives on a new **plan flags** line directly
  under that index: `auto` lets the finish protocol squash-merge a stage PR
  into the plan branch itself once checks are green, instead of offering it.
  The plan→main PR is manual in every mode — `merge` is never read at
  closeout. Defaults are `gate: auto` and `merge: manual`, and an absent
  column or line means the default, so every existing plan behaves exactly as
  before. With them come the **group by gate** decomposition rule (`human`
  stages at the front of the graph, the review stage at the end, the
  mechanical middle `auto`), the rule that in unattended mode any would-be
  question becomes `blocked` + runbook rather than a wait, a `--unattended`
  argument on `/plan-run` that declares that mode (`gate: human` stage →
  report and stop; questions → `blocked`), and `/plan-stages` setting `gate`
  per stage from the decomposition and asking one explicit multiple-choice
  question for `merge` (`manual` recommended). The `gate` column is appended last so the
  session-start hook's positional parsing of the index is unaffected.

### Changed

- **The driver reports a session's own mid-stage block instead of shrugging at
  it** (#98). A session that writes its own `### S<N>` section to
  `.plan/BLOCKED.md` is now recognised the moment its session exits: the driver
  names the block, the stage branch and its PR, and stops. Previously that stage
  simply vanished from the next round's runnable set and the run ended on the
  generic "nothing runnable" message. No retry behaviour changed — the round-start
  override from #89 already kept a listed stage from being relaunched, and the
  retry cap is untouched. `.plan/BLOCKED.md`'s own header now says both the driver
  and a stage session write there; existing files keep the header they were
  created with.

- **Closeout clears finished stage worktrees instead of refusing to close over
  them** (#86). One rule, two modes: a stage worktree whose branch is merged with
  nothing unpushed is finished work — interactive closeout now **offers** to
  remove it, and unattended closeout removes it. Anything holding unpushed
  commits, a stash, an unmerged branch or a modified tracked file is still a hard
  stop in both modes, still reported with its path and contents, and still never
  removed with `--force`. Previously a surviving worktree of any kind refused
  closeout outright and had to be cleared by hand.

- **License changed from MIT to FSL-1.1-ALv2** (Functional Source License).
  Every use stays free except offering the plugin in a competing commercial
  product, and each release automatically becomes Apache-2.0 two years after it
  is made available. Versions released before this change remain MIT.

### Fixed

- **The driver no longer declares a plan complete over a stage that never ran.**
  `scripts/plan_driver.py` counted open stages from `LEDGER.md` rows only, so a
  stage present in `PLAN.md`'s stage index with no ledger row (the shape a
  review stage leaves when it adds the index row and forgets the ledger row)
  was neither runnable nor open — with that as the last stage, the driver
  reported "plan complete" and launched closeout. The reverse shape, a ledger
  row with no index row, stalled forever as "nothing runnable" with no hint
  why. Open stages are now the union of both tables, and the stop message
  names each half-registered stage and which row to add. Also: the Windows
  branch of the driver's shell quoting mangled a value ending in a backslash
  (it reached the real notify command, not only the log) and now uses
  `subprocess.list2cmdline`; and the default `--allowedTools` profile names the
  subagent tool `Agent`, its current name, instead of the retired `Task` — the
  README copy of the profile too.

- **Documentation brought back in step with the protocol.** The `uptime-page`
  example `.plan/` regains the two edits that landed after its last resync —
  preflight step 0.5's "a row this session's own preflight just self-healed is
  a finished stage" sentence and the `BLOCKED.md` entry in its README; the
  `/plan-run` end announcement and the README's dependency-gate line say a
  prerequisite must be `done` **or `skipped`**, as every other surface has
  since the skipped-stage fix; the scaffolded `.plan/README.md` names the
  `merge: auto` carve-out next to "merges are offered", since it is the file a
  plan's human actually reads; and the session-start nudge's "nothing
  runnable" message points at `.plan/BLOCKED.md` as well as the ledger.

- **The driver's `blocked` write no longer makes its own runbook unmergeable**
  (#89). When a stage ran out of attempts, `scripts/plan_driver.py` wrote the
  `blocked` row and runbook straight into `.plan/LEDGER.md` on the plan branch
  — but by then the stage had usually already committed its own edits to that
  same row and notes on its own branch (real acceptance evidence, or a PR that
  opened but couldn't merge), so the two diverged and the stage's pull request
  went `CONFLICTING`. The runbook then instructed a human to merge a PR that
  could no longer be merged. The driver now records a retry-cap block in a new
  sibling file, `.plan/BLOCKED.md`, that the stage branch never edits, so the
  two writers never contend for the same lines; every driver round still
  treats a stage listed there as `blocked` and never retries it, even across a
  restart, regardless of what its `LEDGER.md` row reads. The runbook now also
  says what happens after a hand merge — the row keeps reading `doing` until a
  session's preflight records it `done` — and `/plan-run` (step 5) and the
  template `PLAN.md` (protocol step 0.5) now state that a row the session's
  own preflight just self-healed is a finished stage, not a redo, so relaunching
  it unattended no longer risks a spurious `blocked`. The `.plan/README.md`
  template lists the new file. Verified with a git fixture reproducing #85's
  exact shape (a stage branch with its own unmerged `LEDGER.md` commit): the
  old write conflicted on merge as reported, the new one merges clean.

- **A `skipped` stage no longer deadlocks the stages that depend on it** (#87).
  `deps_satisfied()` in `scripts/plan_driver.py` required a dependency to be
  exactly `done`, while the same file already treated `skipped` as terminal
  everywhere else — so a plan that skipped a stage with dependents reported
  "nothing runnable" and blamed an unmet dependency that was actually settled,
  with no way out short of hand-editing the ledger. `skipped` now satisfies a
  dependent's `depends`, matching the completion rule already stated in
  `skills/staged-rollout/references/templates/PLAN.md` and `SKILL.md`; the
  `Dependency gate` preflight step and the ledger's `skipped` note now also
  flag that a skip can leave acceptance/verification work unowned, for the
  final review stage to catch. Same code path: the "nothing runnable" stop
  message now uses correct singular/plural grammar, and the notify payload's
  stage field is populated with the waiting stages instead of being empty.

## [0.5.0] - 2026-08-21

### Changed

- **`/plan-stages` delegates `.plan/` scaffolding to a subagent.** Step 5 used
  to copy the templates and fill every placeholder directly in the bootstrap
  session — the session already gated on Opus-class for the design work in
  steps 1–4, and by step 5 nothing left is a decision. The scaffolding now
  runs in a dispatched `sonnet` subagent that writes `.plan/` and returns a
  manifest of files written; the `.plan/` ignore check and every git action
  (branch, commit, push, `git ls-files` confirmation) stay in the parent,
  since the ignore check gates on a fix that's the user's call and cannot
  leave the session (#74).

- **`/plan-close` delegates story distillation to a subagent.** Step 3 used to
  read the full `.plan/PLAN.md` and `.plan/LEDGER.md` — the largest material
  the command touches — directly into the closeout session, where it then sat
  resident through cleanup, the final PR proposal, and the end announcement,
  even though nothing after step 3 needs it. The distillation now runs in a
  dispatched `sonnet` subagent that returns PR body text only (no file writes,
  no `git`, no `gh`); every write stays in the parent, and dispatch happens
  only after step 2's completion gate has passed (#73).

### Added

- **Worktree-per-stage is now part of the frozen git model.** The clone stays
  parked on the plan branch for the life of the plan — *the clone holds the
  plan; worktrees hold the work* — and every stage branch is checked out only
  in its own sibling worktree (`../<repo>-s<N>`). Parallel stages were already
  semantically safe, but two concurrent sessions still shared one working tree
  and contended for `HEAD`; separate worktrees are what make a fanned-out wave
  physically runnable. It also keeps `.plan/` readable and the `done` write
  committable at any moment, without disturbing an in-flight stage.
  `SKILL.md`, the template `PLAN.md`, and both READMEs record it as a fixed
  decision, not a bootstrap question. The protocol gains: a **two-tree rule**
  in preflight (the clone's `HEAD` must be the plan branch; a stage branch
  checked out there is drift), worktree reconciliation that classifies live
  siblings, crashed attempts, and orphans the same way branches are already
  classified, worktree provisioning at protocol step 4 (native harness
  mechanism first, `git worktree add` as fallback, and never a silent
  degradation to checking out in the clone), and **teardown** at finish step
  5 — a clean, fully-pushed worktree is removed with its merged branch, while
  anything uncommitted, unpushed, or stashed is left alone and reported.
  `/plan-close` refuses to close while a stage worktree survives.
- **Releases are now cut by GitHub Actions.** `release-prepare.yml` is run by
  hand from the Actions tab, bumps `version` in `.claude-plugin/plugin.json`,
  rotates `## [Unreleased]` into a dated section with its tag link, and opens
  the release pull request. Merging that pull request triggers
  `release-publish.yml`, which tags the version, cuts the GitHub release using
  that version's changelog section as the notes, and fast-forwards `release`.
  The manual four-step sequence this replaces was easy to half-complete — most
  damagingly by moving `release` without bumping the version, which ships
  nothing and fails silently.
- **Parallel stages are now reported.** The stage index's `depends` column has
  always been a full dependency DAG, but every surface that answered "what's
  next" collapsed it to a single stage, so a plan whose real graph is
  `S0 → {S1, S2, S3}` was executed serially and the operator only noticed by
  reading the index by hand. `PLAN.md`'s finish step 6, `/plan-run`'s end
  announcement, and the `SessionStart` hook now report the **complete runnable
  set** — every `todo` stage whose `depends` are all `done` — each with its
  launch command and recommended model/effort, stating plainly when those
  stages can be run concurrently in separate sessions. `/plan-stages` prints
  the derived **wave structure and critical path** after decomposition and
  warns against serialising `depends` beyond genuine prerequisites. Waves stay
  **derived** from `depends` — no `wave` or `parallel-group` column, because a
  stored copy of the graph is what drifts (#54).
- **Concurrent stages are now safe to run, not just visible.** Reporting a
  fan-out is useless if the protocol still assumes one stage is in flight, and
  three rules broke the moment it wasn't. Preflight step 0.5 now classifies a
  mismatch by *whose* stage it belongs to: drift on the stage this session is
  running still halts it, but another stage's in-flight branch — previously
  read as a crashed session, which would have stopped every parallel session —
  is reported and stepped over, while a genuinely crashed stage stays visible
  in later preflights and in closeout's gate. Finish step 4 specifies the
  merge order for parallel stage PRs: the plan branch is the serialization
  point, they merge one at a time, and the second merger merges the plan
  branch *into* its stage branch and **re-runs the acceptance check** (never
  rebasing or force-pushing — the squash merge discards the merge commit).
  Finish step 5 resolves the race on the `done` ledger commit: edit after the
  fast-forward, replay the commit if the push is rejected, keep both rows on
  conflict, never force-push the plan branch. Write territory between
  logically independent stages is modelled as a `depends` edge — there is
  deliberately no separate field, and `/plan-stages` checks same-wave stages
  for overlapping artifacts at decomposition time. `SKILL.md` also records the
  verdict on `exec: subagent(<model>)` fan-out: viable *within* a stage,
  never as a substitute for parallel sessions, because it collapses N stages
  into one PR and one ledger row and makes per-session cost grow with the
  width of the wave (#54).

## [0.4.1] — 2026-08-17

### Changed

- **Pull requests now require maintainer approval.** Every tracked path is owned
  by `@by-carlos`, allowing public contributions while ensuring the maintainer's
  review is required before changes merge.
- **CI check names and plugin validation are stricter.** Required jobs now use
  the shared `gitleaks` and `validate` names, while plugin validation parses
  frontmatter as YAML and verifies every skill name matches its directory.

### Fixed

- **The stage PR gate could deadlock a plan.** When `.plan/` was untracked or
  `.gitignore`d, a decision- or documentation-only stage produced nothing to
  commit and so could never open the stage PR that its dependents' gate
  requires — the plan could not advance past S0 without overriding its own
  rules. A local-only plan branch was the quieter half of the same failure:
  the preflight's `git fetch` and fast-forward both succeeded while doing
  nothing, forever. `.plan/` being tracked and the plan branch having an
  upstream are now stated as load-bearing invariants and **checked**:
  `/plan-stages` refuses to scaffold into an ignored path, pushes the plan
  branch with `-u`, and verifies the scaffold is tracked; every stage
  preflight re-checks both as a hard gate (protocol step 0.0). The finish
  protocol and dependency gate now state explicitly that ledger evidence is
  itself committable content, so no stage is ever exempt from producing a
  commit and a PR (#43).
- **The weight check misread frontier sessions as mid-tier.** The Model weight
  tiers rubric listed the `claude-fable-*` family as "Sonnet-class", so a
  session on Anthropic's most capable widely released model — priced above the
  Opus generation — was graded *lighter* than a stage flagged `model: opus`.
  Both `/plan-stages` and `/plan-run` would then advise relaunching on a
  heavier session that does not exist, or abort a perfectly valid one. The
  family now sits in the top tier, and the rubric says to place a new family by
  capability and price rather than by where its name sorts (#64).

### Documentation

- **Recorded why `model`/`effort` are launch hints rather than automation.**
  The README's per-stage knobs section now states the platform constraint
  behind the design: as of August 2026 no mechanism available to a session can
  start another session at a chosen model or effort — an agent cannot switch
  its own model, effort is not introspectable, and the desktop app's
  suggested-task chips carry only title/prompt/cwd. The verify-model,
  remind-effort split follows from that limit, so the rationale no longer has
  to be re-derived.

## [0.4.0] — 2026-08-15

### Changed

- **This repository is now the plugin's own home.** It was renamed from
  `by-carlos/claude-plugins` to `by-carlos/plan-staged-rollout` and the plugin
  directory was hoisted to the repo root; `.claude-plugin/marketplace.json` moved
  to a new, catalog-only `by-carlos/claude-plugins` repo. Git history, tags,
  releases and issues are unchanged — this was a rename, not an extraction (#56).
- **Distribution moved from `main` to a `release` branch.** The catalog now
  sources this plugin at `ref: release`, so merging to `main` no longer ships to
  users; a release is an explicit fast-forward of `release` onto a tagged commit.
  Install and update commands are unchanged
  (`/plugin marketplace add by-carlos/claude-plugins`).

### Added

- **`/summary`** — a fixed, skimmable summary format (Context, numbered
  findings, optional Conclusion, optional Notes), invoked only on explicit
  request, not on generic "summarize" asks. Overrides default brevity rules
  while active. Also packaged as a standalone `.zip` for upload to claude.ai
  (Settings → Capabilities → Skills).

### Changed

- **`/work-issue` pre-merge acceptance** — user-verifiable changes must leave
  the exact PR head deployed for maintainer inspection and receive explicit
  acceptance before merge; automated and agent verification no longer count as
  a substitute.

### Removed

- **Standalone skills** (`debloat-context`, `summary`, `triage-issues`,
  `work-issue`) — moved out of `skills/` into a private incubator repo
  (`by-carlos/claude-lab`) so they can be developed and tested through the
  real plugin install path instead of a manual copy into
  `~/.claude/skills/`. They'll return here as a proper installable plugin
  once ready.

## [0.3.0] — 2026-08-04

### Added

- **`/debloat-context`** — a standalone skill that audits the fixed per-session
  context cost of a Claude Code setup (every harness's instruction files, skill
  listings, memory index, settings flags) against real usage measured from local
  transcripts, reports ranked savings, then applies approved trims one gated step
  at a time, verified with `/context` before and after. It checks whether the
  harness already defers tool schemas before recommending any `permissions.deny`
  or `disable*` switch — under deferred loading those save close to nothing — and
  it never removes a settled-decision marker from an instruction file. Sized for a
  cheaper model; only a first deep rewrite of a large, dense instruction file is
  escalated to a top-tier one.
- **Secret scanning in CI** — [gitleaks](https://github.com/gitleaks/gitleaks) runs
  on every push and pull request, with an empty baseline so this clean history stays
  green while anything newly introduced still fails the check (#35).
- **Dependabot** — weekly update checks for the `github-actions` ecosystem (#37, #40).

### Changed

- **`/work-issue`** — tightened the board-status lifecycle: the issue moves to
  `In progress` the moment investigation begins (now also in direct
  `/work-issue <number>` mode, not just `next`); a new `In review` state is set
  once the code is in the PR and every non-merge step is done, so the issue
  sits awaiting verification/go-ahead; and the merge is now explicitly the
  final step — any bundled work ("do x and merge") must finish before merging,
  so a mid-flight error can't auto-close an unresolved issue.
- **`/triage-issue` renamed to `/triage-issues`.** Update any saved invocations.
- **Incremental triage by default.** `/triage-issues` now deep-reads only untriaged
  issues (not `Ready`, not `Effort = human`), cutting tokens and wall-time on
  already-groomed boards. Pass `--full` for the previous exhaustive sweep (re-reads
  every issue and dedups against the whole board).
- **`/triage-issues` leaves other boards alone.** An issue is eligible when it is
  already on the target board **or** carries no Project items at all; one that lives
  on a different Project is reported as externally assigned and excluded rather than
  re-queued. Project identities and field values are gathered in a single paginated
  GraphQL query, and `gh project item-list` is avoided during ordinary triage because
  it walks the whole board and can exhaust the hourly GraphQL budget on its own.
- **`plan-staged-rollout`** — documented that the bundled `SessionStart` hook is
  cross-platform (#41).
- **Repo conventions** — added this repository's GitHub issue conventions, including
  the public-repo scrubbing rules, to `CLAUDE.md` (#47).

### Fixed

- **`/triage-issues`** — scoped the incremental gather to open issues, so historical
  `Done` cards no longer make routine queue grooming progressively more expensive (#46).

## [0.2] — 2026-07-13

### Added

- **`/triage-issue`** — a standalone skill that triages open issues across one or
  more repos into a ranked burn-down queue on a GitHub Projects (v2) board. It
  dedups and *consolidates* overlapping issues into single self-contained ones,
  fixes label/field hygiene, and (behind a single go/no-go) sets
  `Status`/`Priority`/`Size`/`Effort` so the board — not a local file — is the
  queue's source of truth. Before ranking, it resolves each issue's
  cross-references and — via `closedByPullRequestsReferences` on any cited,
  already-closed umbrella/parent — detects work whose fix already merged, closing
  it out as completed rather than re-queueing or re-implementing it. Pairs with
  `/work-issue next`.
- **`/work-issue`** — a standalone skill (in `skills/`, installed by copying
  the folder to `~/.claude/skills/` or uploading it to claude.ai / Claude
  Desktop) that works a GitHub issue end-to-end: reads
  the full issue thread, gates on scope (pushes back on multi-session epics and
  trivial one-liners), branches as `<type>/<issue>-<slug>` off a configurable
  base, implements with conventional commits, opens a PR with `Closes #<n>`,
  and squash-merges only after explicit confirmation, tidying up branches
  afterwards. A `next` mode (`/work-issue next`) pulls the top `Ready` issue off
  a `/triage-issue` board queue — ordered by Priority, then Size, then issue
  number — flips it to `In progress` to prevent double-grabs, bounces a too-big
  issue back to `Backlog` so the queue can't loop on it, and on close names the
  next issue and its suggested model.
- **`plan-staged-rollout`:** a worked example of a scaffolded `.plan/` under
  `examples/` — a complete toy project (3 implementation stages + the standing
  final review) captured mid-rollout: a `done` stage with real acceptance output
  pasted as ledger evidence, a `doing` stage with ticked step checkboxes and a
  handoff note, and untouched `todo` stages — plus a tour README of the ledger
  discipline it demonstrates. Linked from the plugin README (#11).
- **`plan-staged-rollout`:** `/plan-stages` bootstrap now computes the modal `model`
  across the stage index and, when a strict majority of stages share one, recommends
  setting it as the session default (and notes it in the scaffolded `.plan/README.md`)
  so the per-stage weight gate only prompts on the exceptions. Bootstrap-time
  convenience only — the stage index stays the authoritative, individually-checked
  home for each stage's `model`/`effort` (#18).
- **`plan-staged-rollout`:** a `.plan/`-aware `SessionStart` hook — opening a fresh
  session in a repo with an active staged rollout now automatically surfaces the
  rollout and its next runnable stage (a `doing` stage to resume, else the first
  `todo` whose `depends` are all `done`), with the stage's recommended model/effort
  and the exact `/plan-run` invocation. It offers, never auto-runs — the weight
  check and dependency gate in `PLAN.md` still govern execution. No `.plan/` in the
  repo → the hook emits nothing; malformed files or parse ambiguity fail silent
  (#13). Cross-platform via the polyglot `run-hook.cmd` wrapper (Windows cmd.exe +
  Unix), mirroring Superpowers' hook layout.

### Fixed

- **`plan-staged-rollout`:** stage sessions and closeout now run a **Preflight & sync**
  block (defined once in the template `PLAN.md`'s operating protocol) before trusting
  the ledger — fetch, fast-forward the plan branch, clean-tree and HEAD-position
  checks, and a ledger-vs-reality reconcile that reports and stops on drift instead of
  auto-repairing (#4; instances #3, #6, #16, #17, #19).
- **`plan-staged-rollout`:** `/plan-run` and `/plan-close` locate the plan via
  `plan-*` branches when `.plan/` is not in the working tree, instead of advising a
  second bootstrap (#3); `/plan-close`'s completion gate also fails on open or
  unmerged stage PRs (#6).
- **`plan-staged-rollout`:** stage PRs pin their base to the plan branch
  (`gh pr create --base plan-<slug>`) (#17); the ledger `done` edit moves to the plan
  branch after the stage PR merges (#19); redo of a `done` stage cuts a fresh
  `-redo-<K>` branch from the plan branch tip.
- **`plan-staged-rollout`:** the `PLAN.md` stage index is now the single authoritative
  home for each stage's `depends` / `mode` / `exec` / `model` / `effort`; stage files
  no longer restate them, ending the two-copies-that-drift ambiguity. Adding a
  PLAN.md stage index row is now a required part of a review-spawned stage's outcome,
  so `/plan-run`'s weight check and next-runnable logic can see it (#5).

## [0.1.0] — 2026-07-10

Initial public release of the `carlos-plugins` marketplace.

### Added

- **`plan-staged-rollout` plugin (0.1.0)** — run big builds as many small, resumable
  sessions instead of one huge one. Decomposes a project into dependency-ordered
  `.plan/` stages with an evidence ledger, then executes one stage per fresh session.
  - Commands: `/plan-stages` (design + decompose an idea), `/plan-run` (execute one
    stage), `/plan-close` (final PR and cleanup).
  - Bundled `staged-rollout` skill documenting the method, the git model, and when
    *not* to use it.
- Marketplace manifest, root and plugin READMEs, and MIT license.

[Unreleased]: https://github.com/by-carlos/plan-staged-rollout/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.5.0
[0.4.1]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.4.1
[0.4.0]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.4.0
[0.3.0]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.3.0
[0.2]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.2
[0.1.0]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.1.0
