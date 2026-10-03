# AGENTS.md — `plan-staged-rollout`

**Read [`CLAUDE.md`](CLAUDE.md) — it is the single source of project context and
guardrails for this repository, and it applies to you in full.** Despite the
filename it is not Claude-specific: it covers the layout, validation, git and
merge conventions, the release/distribution model, the secret-scanning setup,
and the issue-filing contract for this public repo. Release mechanics are in
[`.github/workflows/CLAUDE.md`](.github/workflows/CLAUDE.md).

This file exists so that agents and review tools which bootstrap from
`AGENTS.md` find that pointer. It is deliberately **not** a second copy — a
duplicated ruleset drifts.

## Non-negotiables, restated here so they cannot be missed

These are the rules where *not having read the doc yet* is itself the failure
mode. They are also in `CLAUDE.md`; that copy is authoritative.

- **`release` is live distribution; `main` is not.** Never move `release`
  without bumping `version` in `.claude-plugin/plugin.json` — an unbumped
  fast-forward ships nothing and **fails silently**. Rollback is forward-only;
  never force-push `release`.
- **Never push directly to `main`, and never merge unilaterally** — propose the
  merge and wait for the maintainer's OK.
- **This repo is public.** Scrub issue bodies of hosts, IPs, personal paths,
  tokens and raw logs, and get an explicit OK on the rendered body before
  filing — every time.
