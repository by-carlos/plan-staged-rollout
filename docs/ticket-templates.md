# Customizing the ticket template

[Home](../README.md) · [Install](install.md) · [Staged rollout](staged-rollout.md) ·
[Cloud runs](ON-THE-RUN.md) · [Tickets](tickets.md) · [FAQ](faq.md) ·
[Reference](reference.md)

`create-issue` and `work-issue` write and read tickets in the shape a
**template** describes: which sections a ticket has, the title rules, the
priority and size scales, and how a branch is named. You do not need one. With
no configuration the skills use the built-in default and say nothing.

This page is the short path to your own template. The full field list is in
[`tickets/references/template-schema.md`](../tickets/references/template-schema.md).

## Start from the default

The built-in default is not copied to your machine; the skills read it from
inside the plugin on every run. To change it, write a small file of your own
that **extends** it and states only what differs:

```toml
# ~/.claude/templates/my-team.toml
schema = 1
name = "my-team"
extends = "default"

[title]
max_length = 60

[types]
allowed = ["Story", "Task", "Bug"]
default = "Task"
```

Anything you do not set is inherited from the default. Two merge rules to
know:

- Tables merge key by key, so the example above changes two things and keeps
  the rest.
- Arrays and single values **replace**. To add a section to `body.sections`
  you restate the whole list; copy it from
  [`tickets/templates/default.toml`](../tickets/templates/default.toml) and edit.

## Point the skills at it

Set `ticket_template` in the plan-staged-rollout config file:

| Scope | File |
|---|---|
| You, on this machine | `$CLAUDE_CONFIG_DIR/plan-staged-rollout.toml`, else `~/.claude/plan-staged-rollout.toml` |
| A whole team, in one repo | `<repo>/.claude/plan-staged-rollout.toml` (commit it) |

```toml
ticket_template = "templates/my-team.toml"
```

A relative path resolves against the config file's own directory. Use a table
when you work with both trackers:

```toml
ticket_template = { github = "templates/mine.toml", jira = "templates/team.toml" }
```

The repo file overrides the user file key by key, so a repo can change one
tracker's template and inherit the other.

## Check it

```
python <plugin>/tickets/scripts/ticket_template.py validate <your-template.toml>
```

The plugin directory is under your Claude config folder, in
`plugins/cache/`. A template that is missing or invalid never stops a run: the
skill prints one notice that names the path and the first error, then uses the
built-in default.

## Keep private details private

Field ids, board names and internal project keys belong in a private template
file on your machine or in a private repo, not in a public one.
