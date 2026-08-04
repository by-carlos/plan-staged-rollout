# Changelog

All notable changes to this marketplace are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the `plan-staged-rollout`
plugin follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`/debloat-context`** — a standalone skill that audits the fixed per-session
  context cost of a Claude Code setup (CLAUDE.md files, skill listings, memory
  index, settings flags) against real usage measured from local transcripts,
  reports ranked savings, and applies approved trims one gated step at a time,
  verified with `/context` before/after. Designed to run on a cheaper model.

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

[0.2]: https://github.com/by-carlos/claude-plugins/releases/tag/v0.2
[0.1.0]: https://github.com/by-carlos/claude-plugins/releases/tag/v0.1.0
