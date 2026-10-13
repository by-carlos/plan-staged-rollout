# Contributing

Thanks for your interest in improving this plugin. This is a small, solo-maintained
project, so the workflow is deliberately lightweight.

## Workflow

1. **Open an issue first** for anything non-trivial — a bug, a feature idea, or a
   behavior change. It saves you from building something that won't be merged. Typo
   fixes and other small changes can skip straight to a PR.
2. **Fork** the repo and branch off `main` (e.g. `fix/…`, `feat/…`, `docs/…`).
3. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat:`, `fix:`, `docs:`, `chore:`, …) with clear, present-tense messages.
4. **Open a PR** against `main`. Keep it focused — one logical change per PR — and
   describe what changed and why.

The maintainer ([Carlos Eng](https://github.com/by-carlos)) reviews and merges all PRs.

**Where an install problem goes.** This repository is its own marketplace, so
anything wrong with `claude plugin marketplace add by-carlos/plan-staged-rollout`
— or with the plugin it serves — belongs here. A problem with the shared
`carlos-plugins` catalog listing belongs in
[`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins),
which owns that catalog.

## Validation

A GitHub Actions workflow (`.github/workflows/validate.yml`) runs on every PR and on
pushes to `main`. It runs `scripts/validate_plugin.py`, which checks that:

- `.claude-plugin/plugin.json` parses as JSON and carries `name`, `description` and
  an `x.y.z` semver `version`.
- `commands/*.md` have a `description` and `skills/*/SKILL.md` have `name` and
  `description` in their frontmatter.
- The templates referenced by each `SKILL.md` (`PLAN.md`, `LEDGER.md`, `stage-N.md`,
  `README.md`) exist under `references/templates/`.
- Relative links in `README.md` files resolve.

The script is stdlib-only Python (no external dependencies). Run it locally before
pushing:

```
python3 scripts/validate_plugin.py
```

## Ground rules

- Match the existing style and structure of the code you're touching.
- Update the relevant README and `CHANGELOG.md` when your change is user-facing.
- Be respectful and constructive — assume good faith on all sides.

## Status and layout

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
    stage-run.md                 # /stage-run <N>       — execute one stage, in this session
    plan-run.md                  # /plan-run             — drive every remaining stage remotely
    plan-close.md                # /plan-close          — final PR + cleanup
  skills/create-issue/SKILL.md   # draft, review, post and verify one ticket
  skills/work-issue/SKILL.md     # work one named ticket to a confirmed merge
  tickets/
    scripts/                     # template loader, core, GitHub and Jira adapters
    references/                  # template schema, adapter contract, gap rubric
    templates/default.toml       # the built-in ticket template
    fixtures/  tests/            # dry-run inputs and unit tests
  hooks/
    hooks.json                   # SessionStart and PreToolUse registration
    run-hook.cmd                 # polyglot cmd/bash wrapper (Windows + Unix)
    session-start                # .plan/-aware nudge: next runnable stage
    gh-body-guard                # denies gh body shapes that corrupt non-ASCII
```
