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
