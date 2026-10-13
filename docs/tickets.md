# Tickets — `create-issue` and `work-issue`

Two skills for the unit of work below a plan: one GitHub issue or one Jira
ticket.

- **`create-issue`** turns an ask into one well-formed ticket. It drafts the
  body, has a cheap Sonnet-tier reviewer challenge the gaps, proposes a size
  or story points and a priority, and posts only after you approve. Then it
  reads the ticket back and diffs every field, repairing once. The default
  body is *In plain terms / Context / Out of scope / Acceptance Criteria*,
  plus an optional *AI prompt*.
- **`work-issue`** works one ticket that you name. If the ticket has an *AI
  prompt*, it reads the thread, branches, implements and opens a pull
  request, and it merges only after an explicit yes. Without an AI prompt it
  is guide-only: an interpretation and a step plan, with no branch and no
  writes. Push and merge each have their own gate. Say "work issue 12" or invoke
  `/plan-staged-rollout:work-issue <ticket>`; it never starts on its own.

GitHub goes through `gh`; Jira goes through the Atlassian MCP server (v1 or
v2, detected at runtime). The scripts need Python 3.11 or later and the
standard library only. A `PreToolUse` hook, `gh-body-guard`, denies the `gh`
argument shapes that silently corrupt a non-ASCII issue body.

**Team conventions are a template, not a fork.** With no configuration, the
built-in default template applies. To use your own, set `ticket_template` in
`$CLAUDE_CONFIG_DIR/plan-staged-rollout.toml` (falling back to
`~/.claude/plan-staged-rollout.toml`). A `<repo>/.claude/plan-staged-rollout.toml`
overrides it key by key. The value is a path, or a table
`{ github = "...", jira = "..." }` when you use both trackers. A template
that is missing or invalid gives one notice, then the default applies. What a
template can set — sections, story-point matrix, guarded fields, board
routing, merge command — is in
[`tickets/references/template-schema.md`](../tickets/references/template-schema.md).
Keep your organization's field ids and names in a private template file, not
in a public repo. New to this? Start with
[Customizing the ticket template](ticket-templates.md).

## `work-issue` or a plan?

- **One ticket, one to three sessions of work** → `work-issue`. The ticket's
  acceptance criteria are the gate and its AI prompt is the instruction.
- **Four or more sessions, with dependencies and design worth freezing** →
  bootstrap a plan. A plan's stages are not tickets, and nothing links them
  to tickets yet.
- **A ticket that grows past that while you work it** → stop and bootstrap a
  plan, with the ticket as its origin. Don't stretch one branch across days.
