# claude-plugins

Carlos Eng's [Claude Code](https://code.claude.com/docs/en/overview) plugin
marketplace (`carlos-plugins`).

## Plugins

### [plan-staged-rollout](plan-staged-rollout/README.md)

**Run big projects as many small sessions — not one huge one.**

Breaks a large build into *stages*, executes each stage in its own fresh
session, tracks progress in an evidence-based ledger, and keeps every decision
in exactly one place so the plan never drifts. Sessions stay cheap, progress
stays visible, and you can stop and resume whenever you have time.

```
/plan-stages <idea>  →  design + decompose into .plan/ (once)
/plan-run 3          →  execute one stage in a fresh, cheap session (repeat)
/plan-close          →  final PR, cleanup, done
```

See the [plugin README](plan-staged-rollout/README.md) for the full method,
the git model, and when *not* to use it.

## Install

From within Claude Code:

```
/plugin marketplace add by-carlos/claude-plugins
/plugin install plan-staged-rollout@carlos-plugins
```

Installed plugin commands are namespaced, e.g.
`/plan-staged-rollout:plan-stages`.

## Bonus: standalone skills

The [`skills/`](skills/) directory holds standalone skills that aren't part
of any plugin — install one by copying its folder into `~/.claude/skills/`
(Claude Code, where it's also invocable as a slash command), or upload the
folder to claude.ai / Claude Desktop.

### [/debloat-context](skills/debloat-context/SKILL.md)

**Audit and trim per-session context overhead** — measure what actually loads
(CLAUDE.md files, skill listings, memory index, settings flags) against real
usage from local transcripts, report ranked savings, then apply approved trims
one gated step at a time, verified with `/context` before/after. Sized to run
on a cheaper model.

```
/debloat-context  →  audit, report, then gated trims for user level + current repo
```

### [/triage-issues](skills/triage-issues/SKILL.md)

**Triage issues into a burn-down queue** — sweep open issues across one or more
repos, dedup and *consolidate* overlaps, fix label/field hygiene, and rank the
survivors onto a GitHub Projects (v2) board (`Status` / `Priority` / `Size` /
`Effort`) so `/work-issue next` can work them one at a time. Every write waits
for a single go/no-go.

```
/triage-issues                                    →  triage the current repo's board
/triage-issues by-carlos/linux by-carlos/openwrt  →  triage several repos onto one board
```

### [/work-issue](skills/work-issue/SKILL.md)

**Work a GitHub issue end-to-end** — read the full thread, sanity-check the
scope (pushes back on epics and one-liners), branch as
`<type>/<issue>-<slug>`, implement with conventional commits, open a PR that
closes the issue, and squash-merge only after explicit confirmation. `next` mode
pulls the top issue off the `/triage-issues` queue and works it.

```
/work-issue 42          →  work issue #42, based on main
/work-issue 42 develop  →  same, based on develop
/work-issue next        →  pull and work the top issue from the triage queue
```

## Author

Built by **Carlos Eng** —
[GitHub](https://github.com/by-carlos) ·
[LinkedIn](https://www.linkedin.com/in/carlos-eng/)

## License

[MIT](LICENSE) © Carlos Eng
