# AGENTS.md — `plan-staged-rollout`

**Read [`CLAUDE.md`](CLAUDE.md) — it is the single source of project context and
guardrails for this repository, and it applies to you in full.** Despite the
filename it is not Claude-specific: it covers the git and merge conventions, the
release/distribution model, the secret-scanning setup, and the issue-filing
contract for this public repo.

This file exists so that agents and review tools which bootstrap from
`AGENTS.md` find that pointer. It is deliberately **not** a second copy — a
duplicated ruleset drifts, and sibling repos in this estate have already been
bitten by exactly that.

## Non-negotiables, restated here so they cannot be missed

These are the rules where *not having read the doc yet* is itself the failure
mode. They are also in `CLAUDE.md`; that copy is authoritative.

- **`release` is live distribution; `main` is not.** Two marketplaces serve
  this plugin — the
  [`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins)
  catalog and this repo's own `.claude-plugin/marketplace.json` — and both
  source it at `ref: release`, so nothing reaches users on either route until
  `release` moves. Merging to `main` is safe and ships nothing, and editing
  `marketplace.json` ships nothing on its own either.
- **Never move `release` without bumping `version` in
  `.claude-plugin/plugin.json`.** Claude Code decides whether to update an
  installed plugin by comparing version strings — an unbumped fast-forward ships
  nothing and **fails silently**, which is worse than not shipping at all.
- **Rollback is forward-only.** Revert on `main`, bump the patch, tag, release,
  fast-forward. **Never** point `release` at an older commit, and never
  force-push it.
- **Changelog as-you-go, under `## [Unreleased]`.** Never write a
  dated/versioned heading or bump `plugin.json` mid-batch — that recreates
  version drift. A release is one atomic change: bump, rename the heading, tag,
  fast-forward.
- **Merge model:** squash by default, but the staged-rollout flow overrides it —
  stage PRs into the plan branch (`plan-<slug>`) are **squash-merged**, and the
  final plan-branch → `main` PR is a **normal (non-squash) merge** so each stage
  lands as a distinct commit. `release` is permanent and never deleted.
- **Never push directly to `main`, and never merge unilaterally** — propose the
  merge and wait for the maintainer's OK.
- **This repo is public.** An issue body is published the moment it is filed and
  stays indexed even if edited or deleted. Scrub hostnames, LAN IPs, subnets,
  CT/VM names, personal filesystem paths, and raw log pastes; redact to generic
  placeholders. Show the rendered body and get an explicit OK before filing —
  every time, never waived by a general "capture these".
- **Never cross-post homelab evidence here.** Restate a bug from the plugin's
  side and leave estate detail in the private repo, cross-referenced by number.

Everything else — and the reasoning behind these — is in
[`CLAUDE.md`](CLAUDE.md).
