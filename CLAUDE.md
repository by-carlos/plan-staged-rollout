# CLAUDE.md — plan-staged-rollout

Project instructions for agentic coding in this repository. This repo is the
home of the **`plan-staged-rollout`** Claude Code plugin and nothing else — the
plugin lives at the repo root. It is distributed through **two** marketplaces,
both sourcing it from this repo's `release` branch: the separate
[`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins)
catalog, and this repo's own `.claude-plugin/marketplace.json`, which makes it
installable standalone with
`claude plugin marketplace add by-carlos/plan-staged-rollout`.

## Layout

- `skills/staged-rollout/` — the core skill; `commands/` — the slash commands
  (`plan-stages`, `stage-run`, `plan-run`, `plan-close`).
- `hooks/` — the session-start hook; `scripts/` — validation and release scripts.
- `examples/` — sample `.plan/` folders; `docs/` — user documentation.
- `.github/workflows/` — CI and the release pipeline; its
  [`CLAUDE.md`](.github/workflows/CLAUDE.md) holds the release mechanics.

## Validate and commit

- Run `python3 scripts/validate_plugin.py` before pushing; CI runs the same
  check. It also rejects any tracked text file that is not valid UTF-8.
- Commit with [Conventional Commits](https://www.conventionalcommits.org/) —
  the release bump is inferred from them. Details in
  [CONTRIBUTING.md](CONTRIBUTING.md).

## Git & merge conventions

- **Merge strategy:** Default to **squash merge** for pull requests, unless a
  skill/workflow in this repo specifies a different merge type, or the
  maintainer asks for one.
- **Branch cleanup:** After a branch is merged, **delete it** by default to keep
  the branch list tidy — unless the workflow says to keep it or the maintainer
  asks otherwise. `release` is a permanent branch and is never deleted.
- **Exception — staged rollouts:** this plugin defines its own merge model that
  overrides the squash default for the final integration. Stage PRs into the plan
  branch (`plan-<slug>`) are **squash-merged**; the final PR from the plan branch
  into `main` is a **normal (non-squash) merge**, so each stage lands as a
  distinct commit on `main`. See
  [skills/staged-rollout/SKILL.md](skills/staged-rollout/SKILL.md).
- Merging is never unilateral: propose the merge and wait for the maintainer's OK.
  Never push directly to `main`.

## Filing issues — this repo is public

- An issue body is published the moment it is filed, and stays indexed even if
  edited or deleted afterwards.
- **Scrub before filing.** No hostnames, LAN IPs or subnets, VM/container
  names, personal filesystem paths, email addresses, tokens, or raw log/console
  pastes. Redact to generic placeholders (`<host>`, `10.x.x.x`,
  `/path/to/repo`) and keep the reproduction abstract enough to stand on its own.
- **Show the rendered body and get an explicit OK before filing — every time.**
  This gate is not waived by a general "capture these" from the maintainer;
  public is a one-way door.
- **Restate bugs found elsewhere from the plugin's side** — the behaviour, the
  inputs, the expected result. Leave detail from private projects there,
  cross-referenced by number rather than quoted.

## Secret scanning

[gitleaks](https://github.com/gitleaks/gitleaks) runs in CI on every push/PR
([`.github/workflows/gitleaks.yml`](.github/workflows/gitleaks.yml)); known
historical findings would be baselined in
[`.gitleaks-baseline.json`](.gitleaks-baseline.json) (currently empty — clean
history) so CI stays green on dead history while still catching anything new.
No local pre-commit hook — dev environments vary, so this is CI-only by design.

## Releasing

- **`release` is live distribution; `main` is not.** Both marketplaces source
  this plugin at `ref: release`, so nothing reaches users until `release`
  moves. Merging to `main` is safe and does not ship. `release` is only ever
  **fast-forwarded** to a commit on `main` that has been tagged and released.
- **The standalone marketplace releases on the same move, with no extra step.**
  `.claude-plugin/marketplace.json` is the listing a user gets from
  `claude plugin marketplace add by-carlos/plan-staged-rollout`, and its entry
  also pins `ref: release` — so a fast-forward of `release` ships to both
  routes at once, and editing that file never ships anything on its own. Keep
  its `description` matching `plugin.json`'s rather than leaving two answers to
  one question.
- **Never move `release` without bumping `version` in
  `.claude-plugin/plugin.json`.** Claude Code decides whether to update an
  installed plugin by comparing version strings — if two refs resolve to the
  same version, it skips the update. An unbumped fast-forward therefore ships
  nothing and **fails silently**, which is worse than not shipping at all.
- **Rollback is forward-only.** To undo a released change: revert it on `main`
  as a normal commit, bump the patch version, tag, release, and fast-forward
  `release` onto it. **Never** point `release` at an older commit and never
  force-push it — consumers on the newer version string would not downgrade,
  and the branch history would no longer match any released tag.
- **Changelog as-you-go, under `## [Unreleased]`.** Add entries to `CHANGELOG.md`
  under an `## [Unreleased]` heading as changes land. This records *what* changed
  without declaring a version. Never write a dated/versioned heading or bump
  `plugin.json` mid-batch — that recreates version drift.
- **A release is one atomic change, and GitHub Actions performs it** — never by
  hand. The workflows, the bump rules, changelog heading format, codenames and
  tags are in [`.github/workflows/CLAUDE.md`](.github/workflows/CLAUDE.md).
