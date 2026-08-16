# Changelog

All notable changes to the `plan-staged-rollout` plugin are documented here. The
format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
plugin follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Entries before 0.4.0 were made while this repository was the `carlos-plugins`
marketplace and therefore also cover the standalone skills that have since moved
elsewhere. See 0.4.0 for the split.

## [Unreleased]

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

[0.4.0]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.4.0
[0.3.0]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.3.0
[0.2]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.2
[0.1.0]: https://github.com/by-carlos/plan-staged-rollout/releases/tag/v0.1.0
