# CLAUDE.md — plan-staged-rollout

Project instructions for agentic coding in this repository. This repo is the
home of the **`plan-staged-rollout`** Claude Code plugin and nothing else — the
plugin lives at the repo root. It is distributed through the separate
[`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins)
catalog, which sources it from this repo's `release` branch.

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

## Capturing follow-up work (GitHub issues)

The generic contract — when to file, the issue body format, labels, and the
Size/Effort discipline — lives in the maintainer's global `CLAUDE.md` /
`AGENTS.md`. This section adds only what is specific to this repo.

- **Tracker & board:** issues live in `by-carlos/plan-staged-rollout` and go to
  the **"Claude Plugins"** project (project 3). Its priority scale is **P0–P4**.
- **That board is shared across every Claude plugin repo**, not scoped to this
  one — `by-carlos/claude-plugins` and `by-carlos/daikenja` file there too. So
  don't read the board as a view of this repo: filter by the Repository field
  before concluding anything about what is open here, and don't assume a
  neighbouring item is ours.
- **This repo is public.** Most of the estate is private; this one ships a
  public plugin, so an issue body is published the moment it is filed — and
  stays indexed even if edited or deleted afterwards.
- **Scrub before filing.** No hostnames, LAN IPs or subnets, CT/VM/container
  names, personal filesystem paths, email addresses, tokens, or raw log/console
  pastes. Redact to generic placeholders (`<router>`, `<nas>`, `10.x.x.x`,
  `/path/to/repo`) and keep the reproduction abstract enough to stand on its own.
- **Show the rendered body and get an explicit OK before filing — every time.**
  This gate is not waived by a general "capture these" from the maintainer;
  public is a one-way door.
- **Never cross-post homelab evidence here.** If a plugin bug was found while
  working in `linux`/`openwrt`/`synology`, restate it from the plugin's side —
  the behaviour, the inputs, the expected result — and leave the estate detail
  in the private repo, cross-referenced by number rather than quoted.

## Secret scanning

[gitleaks](https://github.com/gitleaks/gitleaks) runs in CI on every push/PR
([`.github/workflows/gitleaks.yml`](.github/workflows/gitleaks.yml)); known
historical findings would be baselined in
[`.gitleaks-baseline.json`](.gitleaks-baseline.json) (currently empty — clean
history) so CI stays green on dead history while still catching anything new.
No local pre-commit hook — dev environments vary, so this is CI-only by design.

## Releasing

- **`release` is live distribution; `main` is not.** The catalog sources this
  plugin at `ref: release`, so nothing reaches users until `release` moves.
  Merging to `main` is safe and does not ship. `release` is only ever
  **fast-forwarded** to a commit on `main` that has been tagged and released.
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
- **A release is one atomic change, and GitHub Actions performs it.** Don't do
  these steps by hand — the sequence was easy to half-complete, most
  damagingly by moving `release` without bumping the version.
  1. Run **`release-prepare.yml`** from the Actions tab, choosing a bump of
     `auto`, `patch` or `minor`. It bumps `version` in
     `.claude-plugin/plugin.json`, renames `## [Unreleased]` to
     `## [x.y.z] - YYYY-MM-DD`, adds the `[x.y.z]: …/releases/tag/vx.y.z` link
     and rewrites the `[Unreleased]` compare link, then opens the release pull
     request. It never tags and never touches `release`.
  2. Review and merge that pull request. Merging it pushes to `main`, which
     triggers **`release-publish.yml`**: it notices the version changed, tags
     `vx.y.z`, cuts the GitHub release with that version's changelog section as
     the notes, and fast-forwards `release` to the tagged commit.
- **`release-publish.yml` runs on every push to `main` and does nothing unless
  the version changed**, so ordinary merges are unaffected.
- **Both workflows need the `RELEASE_TOKEN` repository secret** — a personal
  access token with repository write access. The default `GITHUB_TOKEN` cannot
  be used: pushes it makes do not trigger other workflows, so the release pull
  request would never reach `release-publish.yml`.
- **Semver:** a `feat` in the batch ⇒ **minor** bump; only `fix`/`docs`/`chore` ⇒
  **patch**. Pre-1.0, breaking changes go in a minor. The `auto` bump infers
  this by looking for a `feat` commit since the last tag, so pass an explicit
  `minor` or `patch` when you disagree with it.
- **Version headings now use a plain hyphen** — `## [x.y.z] - YYYY-MM-DD` — because
  that is the separator the release scripts write and read. Sections dated
  before this change use an em dash and are left as they are.
- **Tag per released version** (not per commit, not major-only) — the `CHANGELOG.md`
  release links assume a tag exists for each version. Keep the two consistent.
- **Historical wart:** the `v0.2` tag is malformed — it should have been
  `v0.2.0`. It predates this convention and is left as-is rather than aliased,
  so `CHANGELOG.md`'s `[0.2]` link points at `v0.2` deliberately. Every tag from
  `v0.3.0` onward follows `vx.y.z`.
