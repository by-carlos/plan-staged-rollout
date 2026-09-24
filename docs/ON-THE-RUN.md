# On the run — driving a plan from your phone

Historically, a staged rollout runs on your machine: open a session, run one
stage, close it, repeat. **On the run** moves that to the cloud. You keep one
session open — the orchestrator — and it fires each stage as its own cloud
session against your GitHub repo, so a whole build can run while you watch
from your phone. The computer running the orchestrator still has to stay on;
what's gone is a person opening a fresh session for every single stage.

## What it does

You run `/plan-run` in one local Claude Code session, in a clone of your
repository. From there:

1. It reads `.plan/LEDGER.md` on the plan branch to work out which stage can
   run next.
2. It fires that stage as a cloud session, using Claude Code's built-in
   `RemoteTrigger` tool — no script, no credential to set up.
3. The cloud session runs the stage on its own: writes the code, opens a pull
   request, merges it into the plan branch, and records `done` (or `blocked`)
   in the ledger. Nothing it does needs you.
4. The orchestrator checks in every few minutes, watching the run and
   re-reading the ledger, then fires the next runnable stage.

It stops when nothing is left to run, when a stage needs a person, or when a
run goes dead — and hands the last merge, plan branch into `main`, to you by
hand, every time.

## What you need first

- **The plugin installed locally.** `/plan-run` is a command in this session,
  not something that runs by itself.
- **A plan already pushed to GitHub**, with `.plan/RUNNER.md` in it. Build the
  plan the usual way with `/plan-stages` on the branch `plan-<slug>`, and push
  it. `RUNNER.md` is scaffolded automatically for new plans; an older plan
  gets it backfilled from the plugin's template before its first remote fire.
- **Cloud access enabled on your Claude account.** `RemoteTrigger` needs it —
  no claude.ai/code cloud, no remote leg.
- **GitHub connected to claude.ai/code for this repository**, so a fired
  session can clone it and open pull requests through the GitHub MCP server.

## Running it

Type `/plan-run` in your local session. It opens with a plain-language notice
— this drives *every* remaining stage on the cloud, not just one — and waits
for a yes. Say yes, and it starts firing.

While it runs, your local session prints what it's doing: which stage it
fired, the cloud session's link, and its status each time it checks in. You
don't have to watch continuously — leave the terminal open and come back to
it.

Each fired stage is an ordinary cloud session. You can open the link the orchestrator prints, at
[claude.ai/code](https://claude.ai/code), on desktop or the
phone app, and watch it work or read its log while it runs. Nothing about
finding it or opening it is special — it's just another session in your
account's list.

It ends one of two ways: every stage is `done` or `skipped` and it stops and
tells you so, or it hits a `gate: human`/`gate: local` stage, a dependency
that isn't ready, or a dead run, and stops in front of that instead. Either
way, merging the plan branch into `main` is left to you.

## What a cloud stage can't reach

A fired stage runs in a sandbox with no path back to your machine: no LAN, no
local files outside the clone, no local services, nothing you have installed
but not committed to the repo. That's what `gate: local` is for — mark a
stage that needs something only your machine has, and the driver skips it and
tells you to run it yourself.

## When a stage is reported dead or blocked

- **Blocked** means the ledger says so — a `gate: human`/`gate: local` stage,
  or a row the stage itself marked `blocked` with a note. Read the note, fix
  or run what it needs, then re-run `/plan-run` to pick up from there.
- **Dead** means the cloud run ended but the ledger row never moved, even
  after the orchestrator's grace period. The orchestrator reports the session
  id, its claude.ai link, what its log showed, and whether the stage branch or
  its pull request exist on the remote. It never writes to the plan branch on
  the stage's behalf — you decide what happens next: re-fire the stage, fix it
  by hand, or open a normal local session for it.

## Known limits

- **Reasoning effort isn't booked** — `RemoteTrigger` books a stage's
  `model` but has no measured way to book its `effort`, so the `effort`
  column is restated in the fired prompt rather than set. The fired stage
  reads the effort it actually got from `CLAUDE_EFFORT` and blocks on a
  mismatch; when a cloud session reports it empty, the stage says so and
  carries on, since an unreadable effort is not a mismatch.
- **Spent routines aren't cleaned up automatically.** Each fire leaves a
  used-up routine behind; the API can't delete it — clear them out at
  claude.ai/code/routines once a plan finishes.
- **A cloud run can't delete remote branches** (403 from the git proxy), so
  merged stage branches linger on the remote until someone deletes them.
- **No path persists outside the primary clone between tool calls**, so a
  sibling worktree can vanish mid-stage — a cloud run falls back to one
  branch per stage rather than one worktree per stage.
- **Cloud access on the account is a likely prerequisite, not a measured
  one** — `RemoteTrigger`'s availability probably tracks it, but that hasn't
  been checked across account types.
- **Not yet proven end to end.** A single stage fired this way, cold, has
  completed in 3.5 minutes on a fixture repo (1 Sep 2026). The full
  multi-stage `/plan-run` loop — fire, watch, repeat to completion — has not
  yet been run live. Don't treat this as proven beyond that one measurement.

## What was tried before

Two earlier designs didn't make it into the current one: hand-provisioning
one cloud routine per model named in the stage table (what this page used to
describe), and driving stages with a Python script posting directly to the
session-creation API (no native tool, meant hand-maintaining an OAuth
credential — not something a public plugin should ship). `claude --cloud` was
also considered and rejected: it needs an interactive TTY and can't be
scripted or called from a session.

## If you want the details

- [`remote-driver.md`](../skills/staged-rollout/references/remote-driver.md) —
  the authoritative contract: the exact `RemoteTrigger` calls, the poll
  cadence, the dead-run definition, and every refusal.
- [`.plan/RUNNER.md`](../skills/staged-rollout/references/templates/RUNNER.md) —
  what a fired cloud session actually follows to run its one stage.
- [`examples/on-the-run/`](../examples/on-the-run/) — retired prompt
  contracts from the earlier routine-based design, kept only so old links
  resolve.
