# Security Policy

## Reporting a vulnerability

**Do not open a public issue or pull request for a security problem.** This
repository is public, and an issue body stays indexed even after it is edited or
deleted.

Report privately through GitHub:
[**Report a vulnerability**](https://github.com/by-carlos/plan-staged-rollout/security/advisories/new).
That opens a draft advisory visible only to you and the maintainer.

If that form is unavailable, contact the maintainer,
[Carlos Eng](https://github.com/by-carlos), through his GitHub profile and ask
for a private channel before sending any detail.

Include what you can: the affected skill, hook or template, the version from
`.claude-plugin/plugin.json`, the steps to reproduce, and what an attacker
gains. Scrub the report the same way an issue would be scrubbed -- placeholders
instead of real hostnames, paths, addresses or credentials.

Expect an acknowledgement within a week. This is a single-maintainer project
worked on in spare time, so a fix may take longer than that; you will be told
where it stands. Please give the maintainer a reasonable window to ship a fix
before disclosing publicly.

## Supported versions

Only the most recent release is supported. Releases are distributed from the
`release` branch, which the marketplace entry in
[`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins) points
at; `main` is the working branch and is not a distribution channel.

## What is in scope

Plan-staged rollout is a Claude Code plugin: markdown skills, a `SessionStart`
hook, and the `.plan/` scaffold they write into your project. There is no
server and no service of its own. In scope:

- A skill that can be induced to write, commit, push or merge something without
  the approval step its contract requires.
- A skill or hook that reads or writes outside the paths its contract names
  (the project's `.plan/` directory and the repository being worked on).
- The `SessionStart` hook (`hooks/session-start`, `hooks/run-hook.cmd`)
  executing anything derived from repository content rather than from the
  plugin's own files.
- Instructions embedded in content a skill ingests -- a `.plan/` stage file, a
  ledger entry, a plan document carried over from another session -- that
  redirect the skill's behaviour.
- The cloud-session path (`references/cloud-session-api.md` and the stage
  runner): a stage dispatched to a session that runs with credentials or scope
  the contract does not describe.
- A weakness in the release path: the tag, the `release` branch, or the CI
  workflows.
- Secrets or personal data committed to this repository, including in history
  and in test fixtures.

## What is out of scope

- Vulnerabilities in Claude Code, the Claude API, or GitHub Actions themselves.
  Report those to their own maintainers.
- The fact that a skill reads files in your project and writes a `.plan/`
  directory into it. That is the documented purpose, gated on your approval.
- A plan or ledger you authored instructing the plugin to do something you did
  not want. Stage files are yours to review before a run.
- Anything requiring an attacker who already controls your machine or your
  Claude Code configuration.
