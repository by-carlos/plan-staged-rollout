# Install and update

[Home](../README.md) · **Install** · [How it works](staged-rollout.md) · [Cloud runs](ON-THE-RUN.md) · [Tickets](tickets.md) · [Ticket template](ticket-templates.md) · [FAQ](faq.md) · [Reference](reference.md) · [Why](why.md)

**In short:** install it with two CLI commands or from the desktop app's
**Plugins** pane; there is nothing to configure. It runs only in the Claude
Code CLI and the desktop app's **Code** tab, not in Chat, Cowork or
claude.ai. To update, use the CLI: the desktop app does not always notice a
new version.

## Install

This repository is a plugin marketplace in its own right, so you can install
the plugin without adding anything else first.

### Claude desktop app

No terminal needed.

1. In the **Code** tab, click **+** next to the prompt box, then **Plugins**.
2. Click **Add**, enter `by-carlos/plan-staged-rollout` in the **URL** box,
   and click **Sync**. The box takes a GitHub `owner/repo` as it is.
3. The plugin directory opens when the sync finishes. Plan-Staged Rollout is
   under the **Code** tab. Click the **+** beside it to install it.

You enable, disable or remove it later from the same **Plugins** pane.

### Claude Code CLI

From your shell:

```bash
claude plugin marketplace add by-carlos/plan-staged-rollout
claude plugin install plan-staged-rollout@plan-staged-rollout
```

Or from inside a session:

```
/plugin marketplace add by-carlos/plan-staged-rollout
/plugin install plan-staged-rollout@plan-staged-rollout
```

### From the shared catalog instead

The plugin is also listed on the shared
[`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins)
marketplace. Use it if you already have that marketplace added, or you want
its other plugins:

```
/plugin marketplace add by-carlos/claude-plugins
/plugin install plan-staged-rollout@carlos-plugins
```

Both routes install the same plugin from this repository's `release` branch.
The `@<marketplace>` suffix only names where you added the listing from.
Development happens on `main`; what you install comes from `release`.

### After installing

There is nothing to configure. Open a repository with a build too big for one
session and run `/plan-staged-rollout:plan-stages <your project idea>`.
Everything the plugin needs after that, it writes into that repository's
`.plan/` folder. Next: [How a staged rollout works](staged-rollout.md).

Installed plugin commands carry the plugin's name as a prefix
(`/plan-staged-rollout:stage-run`). The other pages use the short names
(`plan-stages`, `stage-run`, `plan-run`, `plan-close`) to stay readable.

## Where it runs

**It is a Claude Code plugin**, so it runs wherever Claude Code does: the
**Claude Code CLI** and the **Code** tab of the **Claude desktop app**, in
local and SSH sessions.

It does not appear in these places:

- the desktop app's **Chat** and **Cowork** tabs, or claude.ai itself: none
  of them run Claude Code plugins;
- a **cloud** session (the desktop app's **Send to cloud**, claude.ai/code, or
  a stage `plan-run` fires): a copy installed on your machine is not there.
  Cloud stages don't need it: they follow `.plan/RUNNER.md`, which every
  plan carries.

Some parts need more than a session:

| Part | Needs | Without it |
|---|---|---|
| [Session-start nudge](staged-rollout.md#session-start-nudge) and the `gh-body-guard` ticket check | `bash` (on Windows, Git Bash). Both hooks run through a cmd/bash wrapper, so they work on Linux, macOS and Windows. | No nudge, and `gh` commands go unchecked. Everything else works: the commands are run by the model, not by shell scripts. |
| [Running a plan in the cloud](ON-THE-RUN.md) | The plan flag `merge: auto`; cloud access on your Claude account (very likely required); and GitHub connected to claude.ai/code for the repo. The orchestrator (the local session running `plan-run`) fires stages through Claude Code's built-in `RemoteTrigger` tool, so there is nothing to install. | No cloud runs. Run stages locally. |
| [Ticket skills](tickets.md) | Python 3.11 or later. `gh` for GitHub; the Atlassian MCP server for Jira. | That tracker is unavailable. |

**Typing `/plan-staged-rollout:<command>` always works.** Plain language
("run stage 3 of the plan") needs Claude Code to have room to read the
command descriptions; a smaller-context model with many plugins installed
may not. If it stops working, use the slash form, or give descriptions more
room with `skillListingBudgetFraction` in your Claude Code settings.

## Update

New versions ship on the `release` branch. A merge to `main` releases nothing.
[CHANGELOG.md](../CHANGELOG.md) lists what shipped when.

However you update, a running session keeps the old version: restart Claude
Code, or run `/reload-plugins`.

### Claude Code CLI (dependable)

From your shell:

```bash
claude plugin marketplace update
claude plugin update plan-staged-rollout
```

Inside a session, `/plugin marketplace update` does the same one-off refresh.

**Turning on auto-update is worth it.** Run `/plugin`, open the
**Marketplaces** tab and select this plugin's marketplace:

- **Enable auto-update** refreshes the marketplace and its plugins in the
  background shortly after each session starts.
- **Update marketplace** does a one-off refresh.
- The tab also shows which state you are in. Check it rather than assume:
  Claude Code turns auto-update on by default for Anthropic's own
  marketplaces, not necessarily for others.

The desktop app has no equivalent toggle, which makes the CLI the reliable
way to stay current.

### Claude desktop app

Open the **Plugins** pane and select the plugin. Its page shows your version
and an **Update** button.

**Do not count on the desktop app noticing a new release.** In testing, a
plugin stayed on an old version across a release: the **Update** button was
inactive and **Check for updates** reported nothing, days after the new
version was out. If the page shows an older version than you expect, remove
the plugin and install it again. A reinstall always lands on the current
version.

### Does updating disturb a plan in progress?

No. A `.plan/` folder carries its own operating protocol inside the `PLAN.md`
that `plan-stages` scaffolded, and `stage-run` is a thin wrapper that defers
to it. A plan keeps running exactly as it was split up, whatever version is
installed when you come back to it. A new version changes what the *next*
`plan-stages` scaffolds, not what a plan in progress does.

What an update *can* change is the plugin-side layer around that protocol:
`stage-run`'s model-tier check and handoff chips, the session-start nudge,
and `plan-run`'s orchestrator loop. None of these is scaffolded into
`.plan/`, so they follow the installed version. What each fired cloud stage
follows is the plan's own `.plan/RUNNER.md`: `plan-run` writes one from the
installed version's template only when a plan has none, and uses an existing
one as it is.
