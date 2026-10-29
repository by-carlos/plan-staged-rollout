# Driving stages locally through herdr — draft contract

**Status: draft, from the issue #223 spike (20–21 Oct 2026, superseded numbering;
see the issue for the dated findings comment this draft accompanies). Not
wired into any command. `/plan-run` still only drives stages on the cloud;
this file is the shape a future `/plan-run --local` (or a separate command)
would follow, written down while the mechanism is fresh.**

This mirrors [`remote-driver.md`](remote-driver.md)'s structure on purpose —
the two should read as one driver with two "fire a stage" / "wait for it"
backends, not two unrelated designs. Shared rules are not restated in full;
where this file says "as remote-driver.md", that section applies unchanged.

## What the local orchestrator is

A session running on the operator's own machine, inside
[herdr](https://herdr.dev) (a terminal multiplexer for coding agents), that
drives a plan's stages by opening a herdr pane per stage, starting Claude
Code in it, and prompting `/stage-run <N> --unattended`. It is not a stage
session itself — like the remote orchestrator, it only reads `.plan/PLAN.md`
and `.plan/LEDGER.md` to decide what is runnable, and treats a stage as done
only once the ledger says so.

## Prerequisites (environment, not herdr)

Stage sessions need a Linux shell with Claude Code's sandbox available. On
Windows that means **WSL2** (Windows Subsystem for Linux, version 2), not
native Windows — confirmed in the spike. Two environment gaps the spike found,
both **must be fixed or worked around before this is safe to run unattended**:

1. **The plugin's `SessionStart` hook fails under WSL2.** It invokes a
   Windows `.cmd` file, which has no interpreter on Linux, so it fails
   "Permission denied" every session start. Non-blocking, but its side effect
   matters: on Windows this hook is what flips a fresh session into Claude
   Code's Auto mode automatically; under WSL2 that never happens, so every
   stage session starts in manual mode and must be switched by hand (see
   *Firing one stage*, below). **Needs a portability fix** (a `.sh`
   counterpart or an OS-aware dispatcher) before this driver can be truly
   hands-off.
2. **A fresh WSL2 Claude Code install carries none of the host's git-push
   safety net.** No `~/.claude/hooks/`, no `permissions.ask` entry gating
   `gh pr merge` on a protected branch. The guard that stops an unattended
   session from pushing to or merging into `main` is a Windows-host-level
   config, not something that travels into WSL2 automatically. **A local
   driver must provision that guard inside WSL2 explicitly** (whatever
   installs it on the host — `carlos:setup-wow` or equivalent — needs its own
   run there) before firing anything unattended. Until then, treat every
   WSL2 stage session as carrying a real, unmitigated risk of pushing to the
   default branch if something goes wrong in the stage protocol itself.

## Firing one stage

For each stage in the runnable set (computed exactly as `plan-run.md` step 4
does, from `.plan/PLAN.md`'s index and `.plan/LEDGER.md`):

```
herdr workspace create --cwd <clone> --label stage-<N> --no-focus
# -> .result.root_pane.pane_id
herdr agent start s<N> --kind claude --pane <pane_id> -- --permission-mode acceptEdits
```

Do **not** pass `--dangerously-skip-permissions`: an orchestrating Claude
Code session's own auto-mode classifier refuses to launch an agent that way,
even into a private throwaway repo — confirmed in the spike. `acceptEdits`
plus Claude Code's own Auto mode (next step) is the supported path, not a
blanket bypass.

Match the stage's declared effort **before** firing — Claude Code's reported
effort is session-internal (`/effort <tier>`), not inherited from the pane's
shell environment; herdr's `workspace create --env` does not set it. Each
model has its own default effort when a session starts fresh (Sonnet: high;
Haiku: medium, confirmed in the spike) — assume a mismatch unless set
explicitly:

```
herdr agent prompt s<N> "/effort <tier from the stage index>" --wait --timeout 20000
```

Then fire the stage:

```
herdr agent prompt s<N> "/plan-staged-rollout:stage-run <N> --unattended" --wait --timeout 60000
```

**Two one-time approvals happen on a session's first live run, nowhere
else — both are expected, both persist (globally, across fresh sessions)
once granted:**

- The first Bash call in the stage protocol stops for approval; its dialog
  offers "Yes, and switch to auto mode" — select it. From then on, Claude
  Code's own classifier evaluates tool calls instead of stopping for a
  human, and in every case observed in the spike it let real stage work
  through while still refusing the unsafe-agent-spawn case above.
- The first time a stage worktree (a sibling directory outside the clone
  Claude Code considers its working directory) is read, one more approval
  fires ("reads outside the working directories") — select "Yes, and keep
  allowing". This is expected: a stage's worktree is always a sibling of the
  clone, by design (`remote-driver.md` and `PLAN.md` both describe this
  layout), so this is not a stage-specific condition to special-case.

A prompt call that returns `agent_prompt_stalled` is not necessarily a
failure — a command that resolves in under ~5 seconds with no visible
"working" state can report stalled even though it succeeded. Check
`herdr agent get <name>` / `agent read` before assuming anything broke.

## Parallel stages

Fire each stage in the runnable set in its own herdr workspace/pane, same as
above, without waiting for earlier ones to settle first — confirmed safe in
the spike: `git worktree add` run concurrently against the same base clone
from separate panes raised no contention, and a second stage's merge
conflicting with a first stage's already-landed `.plan/LEDGER.md` change is
handled by the stage protocol itself (keep both rows), not by this driver.
Nothing extra is needed here beyond firing both and watching both.

## Watching a fired stage to settlement

As `remote-driver.md`'s core discipline: the ledger is the only completion
signal, never the agent's own chat report. Concretely, with herdr:

```
herdr agent wait s<N> --until idle --timeout <generous>
```

then re-read `.plan/LEDGER.md` directly (`git -C <clone> show
plan-<slug>:.plan/LEDGER.md`, or after a fetch/pull) to confirm the row
actually moved to `done` or `blocked` — do not trust `herdr agent read`'s
transcript alone. The spike independently re-checked a stage's actual
artifact and ledger row after every run rather than trusting the agent's own
"finished" summary, and that discipline is the point, not an extra step to
drop once things seem to be working.

## What the local driver refuses

Same list as `remote-driver.md`'s *What the orchestrator refuses*, unchanged:
never fires a stage whose `gate` isn't `auto` or absent; never merges the
plan→main pull request; never writes `.plan/LEDGER.md` or
`.plan/BLOCKED.md` itself — that's the stage session's job, inside the
protocol, not the driver's. Plus one local-specific addition: **never hands a
stage session a full permission bypass** (`--dangerously-skip-permissions`)
to get around the auto-mode-switch dance above — if that one extra
confirmation per session is a real blocker, the fix is the `SessionStart`
hook portability bug, not a wider bypass.

## Known gaps before this is more than a draft

- The two prerequisite fixes above (hook portability, provisioning the
  git-push guard inside WSL2) are not optional hardening — without them this
  driver is firing stages in an environment with real gaps in its own safety
  net, not just a less convenient one.
- `effortlog.py` (the per-stage effort-calibration log) silently no-ops in a
  fresh WSL2 image because only `python3` is on `PATH`, not `python` — minor,
  but means this environment currently contributes no calibration data.
- Not tested: resuming a herdr server across a WSL2 restart, sleep/wake
  behavior, or a remote phone check-in via Tailscale — all out of scope for
  this draft, left to the issue's own open questions.
