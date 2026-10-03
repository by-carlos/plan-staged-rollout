# CLAUDE.md — release mechanics

Applies to work under `.github/workflows/`, the release scripts in `scripts/`,
and any release of this plugin. The distribution rules (`release` is live,
bump before moving it, forward-only rollback) are in the root
[`CLAUDE.md`](../../CLAUDE.md).

## The release sequence

**A release is one atomic change, and GitHub Actions performs it.** Don't do
these steps by hand — the sequence was easy to half-complete, most damagingly
by moving `release` without bumping the version.

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

## Versions, headings and tags

- **Semver:** a `feat` in the batch ⇒ **minor** bump; only `fix`/`docs`/`chore` ⇒
  **patch**. Pre-1.0, breaking changes go in a minor. The `auto` bump infers
  this by looking for a `feat` commit since the last tag, so pass an explicit
  `minor` or `patch` when you disagree with it.
- **Optional codename, hand-added per release.** After `release-prepare.yml` dates
  a section, a `**Codename:** <name>` line may be added as the first line of that
  section's body, before merging the release PR. `release-publish.yml` strips it
  from the release notes and folds it into the release title as `vX.Y.Z (<name>)`.
  This never touches the tag, the heading, or `plugin.json` — those stay plain
  semver — and it's a one-off per release, not something `release-prepare.yml`
  prompts for.
- **Version headings now use a plain hyphen** — `## [x.y.z] - YYYY-MM-DD` — because
  that is the separator the release scripts write and read. Sections dated
  before this change use an em dash and are left as they are.
- **Tag per released version** (not per commit, not major-only) — the `CHANGELOG.md`
  release links assume a tag exists for each version. Keep the two consistent.
- **Historical wart:** the `v0.2` tag is malformed — it should have been
  `v0.2.0`. It predates this convention and is left as-is rather than aliased,
  so `CHANGELOG.md`'s `[0.2]` link points at `v0.2` deliberately. Every tag from
  `v0.3.0` onward follows `vx.y.z`.
