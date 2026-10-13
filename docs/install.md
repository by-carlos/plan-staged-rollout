# Install and update

## Install

This plugin is listed on the shared
[`by-carlos/claude-plugins`](https://github.com/by-carlos/claude-plugins)
marketplace, and this repository is also a marketplace in its own right — so
you can install it on its own, without adding anything else first. Pick
whichever of these matches how you use Claude Code.

### Claude Desktop app

No terminal needed. Open the **Plugins** pane (the **+** button next to the
prompt box, then **Plugins**) and click **Add**. Put
`by-carlos/plan-staged-rollout` in the **URL** box — it takes a GitHub
`owner/repo` directly, so there is nothing else to paste — then click **Sync**.

The plugin directory opens on its own once the sync finishes. Plan-Staged
Rollout is under the **Code** tab, with a **+** beside it — click that, and it
is installed.

The same **Plugins** pane is where you later enable, disable or remove it.

### Claude Code CLI

From inside a session:

```
/plugin marketplace add by-carlos/plan-staged-rollout
/plugin install plan-staged-rollout@plan-staged-rollout
```

Or from your shell, without starting a session first:

```bash
claude plugin marketplace add by-carlos/plan-staged-rollout
claude plugin install plan-staged-rollout@plan-staged-rollout
```

### From the shared catalog instead

If you already have the `carlos-plugins` marketplace added, or you want the
other plugins in it, install from there:

```
/plugin marketplace add by-carlos/claude-plugins
/plugin install plan-staged-rollout@carlos-plugins
```

Both routes install the same plugin from the same `release` branch of this
repository. The `@<marketplace>` suffix is the only difference — it names where
you added the listing from, not what you get. `main` is where development
happens; `release` is what installs.

### After installing

There is nothing to configure. Go to a repository with a build too big for one
session and run `/plan-staged-rollout:plan-stages <your project idea>` —
everything the plugin needs after that, it writes into that repository's
`.plan/` folder itself.

Installed plugin commands are namespaced — see the quickstart above for the
exact commands to type. The rest of this README uses the short names
(`plan-stages`, `stage-run`, `plan-run`, `plan-close`) for readability. Getting a later
version is [Updating](#updating), further down.

## Where it runs

**This is a Claude Code plugin.** It runs everywhere Claude Code does: the
**Claude Code CLI**, and the **Code** tab of the **Claude Desktop app**. You
can install it from either one — the Desktop app has its own plugin menu, so
you never have to open a terminal. Local and SSH sessions both work.

It is not a claude.ai skill. The Claude Desktop app has three tabs, and only
**Code** runs Claude Code plugins — **Chat** and **Cowork** do not, and neither
does claude.ai itself, so the plugin will not appear in any of them. One more
case worth knowing: a desktop **cloud** session loads plugins from your
claude.ai account rather than from your own machine, so a copy you installed
locally will not be there either.

Two parts of the plugin ask for a little more than a session:

- **The session-start nudge needs `bash`.** The hook ships as a cmd/bash
  polyglot wrapper, so it runs on Linux, macOS and Windows via Git Bash. A
  Windows box without bash simply gets no nudge, and nothing else is affected —
  the commands themselves are model-driven, not shell scripts. See
  [Session-start nudge](staged-rollout.md#session-start-nudge).
- **Driving stages remotely needs cloud access on your Claude account.** The
  orchestrator session fires each stage as a cloud session through Claude
  Code's built-in `RemoteTrigger` tool — nothing to install, but an account
  without claude.ai/code cloud has no cloud leg. See
  [Driving a plan remotely](ON-THE-RUN.md#under-the-hood).

**Typing `/plan-staged-rollout:<command>` always works.** Claude Code can also
start one from plain language ("run stage 3 of the plan"), but only when it has
room to read the command descriptions — on a smaller-context model with a lot
of plugins installed it can fall back to names alone, and plain-language
triggering stops working. This plugin's surface is small, so it is an unlikely
squeeze; if it does happen, use the slash form, or give descriptions more room
with `skillListingBudgetFraction` in your Claude Code settings.

## Updating

New versions ship on the `release` branch. A merge to `main` releases nothing.

### Claude Desktop app

Open the **Plugins** pane and select the plugin. Its page shows the version you
have and an **Update** button.

**Do not count on the desktop app noticing a new release.** Its updating has
been inconsistent in testing: a plugin sat on an old version across a release,
with the **Update** button inactive and **Check for updates** reporting nothing
available, days after the new version was out.

So if that page shows a version behind the one you expect, do not wait for it.
Remove the plugin and install it again — a reinstall always lands on the
current version. If you have a terminal, the CLI commands below are the
dependable route.

### Claude Code CLI

Run `/plugin` and open the **Marketplaces** tab. Selecting this plugin's
marketplace gives you **Update marketplace** for a one-off, and **Enable
auto-update**, which has Claude Code refresh the marketplace and its installed
plugins in the background shortly after each session starts. That tab also
tells you which state you are currently in.

Auto-update is worth turning on, and worth checking rather than assuming:
Claude Code enables it by default for Anthropic's own marketplaces, not
necessarily for others. The toggle lives here in the CLI, and the desktop app
has no equivalent — which, with the caveat above, makes the CLI the reliable
way to stay current.

`/plugin marketplace update` does the one-off refresh without opening the tab.
The same two actions from your shell, without starting a session first:

```bash
claude plugin marketplace update
claude plugin update plan-staged-rollout
```

However you update, a new version does not load into a session that is already
running: restart Claude Code, or run `/reload-plugins`.

### Does updating disturb a rollout already in progress?

No. A `.plan/` folder carries its own operating protocol inside the `PLAN.md`
that bootstrap scaffolded, and `/stage-run` is a thin wrapper that defers to
it. A plan therefore keeps running exactly as it was decomposed, whatever
version is installed when you come back to it days later. A new version
changes what the *next* `/plan-stages` scaffolds, not what an in-flight plan
does. `/plan-run`'s own orchestrator loop is the one exception — it isn't
scaffolded into `.plan/`, so a plugin update does change what it does the
next time you run it; what each fired stage runs cold is still
`.plan/RUNNER.md`, versioned and backfilled the same as the rest of `.plan/`.

[`CHANGELOG.md`](../CHANGELOG.md) is what shipped when.
