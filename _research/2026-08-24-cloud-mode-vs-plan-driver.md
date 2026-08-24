# Can Claude Code's cloud features replace `scripts/plan_driver.py`?

Research note, 2026-08-24. Unattended session, no code changed.
Measured against Claude Code **2.1.240** (the version installed on `ranma`) and
the docs at `code.claude.com` as of this date. Routines and Claude Code on the
web are both still labelled **research preview**, so every limit below can move.

**This file is a research note, not repo documentation.** It is deliberately
left untracked under `_research/`. It records what was *proposed*, which per the
maintainer's own rule does not belong in the committed repo. Move it, file it as
an issue, or delete it.

**Outcome — filed 24 Aug 2026 as the "on the run" issue set**
(`by-carlos/plan-staged-rollout`): tracker
[#104](https://github.com/by-carlos/plan-staged-rollout/issues/104), with
sub-issues [#105](https://github.com/by-carlos/plan-staged-rollout/issues/105)
(map the routine configuration surface),
[#106](https://github.com/by-carlos/plan-staged-rollout/issues/106)
(repo-committed skills load in a run),
[#107](https://github.com/by-carlos/plan-staged-rollout/issues/107) (stage git
cycle from a run), [#108](https://github.com/by-carlos/plan-staged-rollout/issues/108)
(stage-runner prompt contract),
[#109](https://github.com/by-carlos/plan-staged-rollout/issues/109)
(orchestrator prompt contract) and
[#110](https://github.com/by-carlos/plan-staged-rollout/issues/110) (end-to-end
proof of concept, blocked by #108 and #109). Start with #105. The design those
issues encode supersedes §6's three tiers: the orchestrator is a
user-credentialed interactive session firing one routine per stage, and the
`gate: human` and plan-to-main gates stay manual.

---

## 1. The question

> The unattended mode of PSR requires a computer and a Python. Claude now
> supports cloud mode, routines, dispatch. Could Claude Code spawn sub-sessions
> and manage them from the desktop app and the phone, replacing the script?

Short answer: **half of it, and not the half that matters most.**

- The **cloud** half removes the computer, and — per the §3.5 correction — a
  session *can* spawn cloud sessions through the routine API. What remains
  unproven is whether a routine-*run* session can do it (worker credentials),
  which decides between a self-advancing chain and an externally-fired one.
- The **local dispatch** half (`claude --bg`, cross-session messaging, agent
  view) genuinely can reproduce the driver loop, and now works on native
  Windows — but it still needs the computer on, and it trades deterministic
  Python for a model-driven loop.
- The part that is **available today at almost no cost** is neither: it is the
  *control and notification* layer (Remote Control + the existing
  `PLAN_DRIVER_NOTIFY` hook), which gives phone visibility and phone answers
  without touching the loop at all.

---

## 2. What the driver actually does

Before judging replacements, the responsibilities, from
[`scripts/plan_driver.py`](../scripts/plan_driver.py):

| # | Responsibility | Where it lives today |
|---|---|---|
| 1 | Parse `.plan/LEDGER.md` + `PLAN.md` stage index; recompute the runnable set every round | `parse_ledger`, `parse_plan`, `runnable_set` |
| 2 | Launch **one fresh `claude -p` session per stage**, with that stage's `--model` / `--effort` from the stage index | `build_command`, `weight_argv` |
| 3 | Apply one shared session profile to every launch — `--permission-mode`, `--allowedTools`, `--plugin-dir`, `--setting-sources`, `--max-budget-usd` | `session_profile` |
| 4 | Wait, re-read the ledger, branch on the new status: `done`/`skipped` continue, `blocked` stops, anything else retries up to `--max-attempts` then writes and commits `.plan/BLOCKED.md` | `drive`, `record_driver_block` |
| 5 | Stop in front of a `gate: human` stage, never launch it | `drive` |
| 6 | Fire `PLAN_DRIVER_NOTIFY` on `stop` / `blocked` / `complete` | `notify` |
| 7 | When everything is settled, launch `/plan-close --unattended`, then confirm the plan→main PR with `gh pr list` — and never merge it | `close_out`, `open_plan_pr` |
| 8 | Refuse to run on a protected branch | `PROTECTED_BRANCHES` |

Two of these are the load-bearing ones:

- **#2 — a fresh session per stage.** This is PSR's entire premise. Context
  isolation per stage is what makes a long build resumable without drift.
- **#4 — a deterministic loop over a file-based ledger.** The ledger is the only
  state, and the code that reads it cannot decide to read it differently today.

Everything else is plumbing that any replacement can reproduce.

---

## 3. What exists now

Verified against the docs and, where noted, against this account.

### 3.1 Routines (cloud)

`claude.ai/code/routines`, `/schedule` in the CLI, or the `RemoteTrigger` API.
A routine = saved prompt + repos + environment + connectors, fired by a
**schedule** (minimum interval 1 hour), an **HTTP POST** to a per-routine token
endpoint, or a **GitHub event** (`pull_request.*`, `release.*`, with filters on
author, title, base/head branch, labels, draft, merged).

Confirmed on this account: `RemoteTrigger action:list` returned HTTP 200 and two
existing enabled routines, so routines are live here and not org-blocked.

Properties that matter for PSR:

- Each fire creates **one new cloud session**. Sessions are never reused across
  events; two events give two independent sessions.
- Runs are fully autonomous: **no permission prompts, no permission-mode
  picker**. Whatever the environment and connectors allow, the run can do.
- One **model selector per routine**, applied to every run. There is no
  per-fire model or effort.
- Repos are **cloned fresh from the default branch** each run. Claude pushes to
  `claude/`-prefixed branches freely; any other branch is checked and rejected
  if it is protected, has someone else's open PR, or carries someone else's
  commits.
- GitHub access goes through a proxy that serves **REST but only a pinned set of
  GraphQL operations** — Projects v2 is unreachable. PSR does not use Projects,
  so this is fine, but `gh` commands that fall back to GraphQL are not.
- VM: Ubuntu 24.04 x86-64, ~4 vCPU / 16 GB / 30 GB, `gh` and Python
  pre-installed, network limited to an allowlist by default.
- Limits: a **daily cap on routine runs per account**, plus per-routine and
  per-account **hourly caps on GitHub webhook events** during the preview.
  Routines draw down the normal subscription usage.

### 3.2 Desktop scheduled tasks (local routines)

The Desktop app's Routines page also creates **local** tasks: run on your
machine, see local files, minimum interval **1 minute**, per-task permission
mode and model, and a built-in **isolated-worktree toggle**. They fire only
while the app is open and the machine is awake; a missed run gets exactly one
catch-up.

### 3.3 Background agents / dispatch (local)

`claude --bg "<prompt>"` starts a real background session — its own context, its
own quota, `--cwd`, `--model`, `--effort`, `--permission-mode`, `--agent` all
available as flags. A per-user supervisor daemon owns them; `claude agents` is
the dashboard. Background sessions auto-isolate into `.claude/worktrees/<id>/`
unless `worktree.bgIsolation: "none"` is set.

Cross-session messaging (`ListAgents` / `SendMessage`) reaches those sessions by
name, and `notify_when_idle` gives **one push when a named local session next
goes idle or exits** — no polling. This is the piece that makes an LLM-driven
driver loop practical rather than a busy-wait.

**Native Windows support landed in 2.1.234**; this machine runs 2.1.240, so it
is available here. Same-machine delivery uses a named pipe and requires the
`CLAUDE_CODE_MESSAGING_TOKEN` auth line on Windows.

### 3.4 Remote Control

`claude --remote-control` (or `/remote-control`) exposes a **local, interactive**
session to `claude.ai/code` and the mobile app. Code and files stay local.
Permission prompts and `AskUserQuestion` dialogs are forwarded and stay open
until answered; other forwarded dialogs expire after `dialogExpiry` (5 min
default). Push notifications to the phone are configurable for "Claude decides"
and "action required".

Note: **Remote Control needs an interactive session.** A `claude -p` stage
session cannot be remote-controlled. The orchestrator can be; the stages cannot.

### 3.5 What does *not* exist — CORRECTED 2026-08-24

- ~~**A cloud session cannot start another cloud session.**~~ **Wrong as first
  written.** The two paths originally checked are genuinely closed —
  `/schedule` is unavailable inside a web session, and `claude --cloud` needs a
  claude.ai OAuth login the sandbox does not hold — but a third path works:
  **the routine API is session-callable.** Verified on this account
  (2026-08-24): a Claude session created a one-off routine
  (`created_via: meta_mcp`, "Hello World Test"), it fired, and it spawned a new
  cloud session. The CLI-side `RemoteTrigger` tool can create/update/run
  routines programmatically, and each routine's `/fire` endpoint is a plain
  HTTP POST with a routine-scoped bearer token — callable with `curl` from
  inside a cloud session, since the Anthropic API is always reachable there.
  **Unverified remainder:** the confirmed spawn came from a *user-credentialed*
  surface (the phone). Whether a session *created by a routine* can fire the
  next routine is untested — the webhook-trigger API "rejects worker
  credentials", which suggests routine-run sessions hold weaker credentials.
  The `/fire` bearer token is routine-scoped rather than user-scoped, so a
  stage run `curl`ing the next stage's endpoint is plausible but unproven.
  This is now the highest-value probe (see §7).
- **A subagent is not a session.** The `Agent` tool takes a `model` override but
  no `effort`, shares the parent's budget and working directory, and reloads
  nothing. It cannot stand in for a fresh `claude -p` stage session.
- **`Agent(isolation: "remote")` is undocumented and gated.** The tool schema
  says it "launches the agent in a remote cloud environment", availability
  gated. **Not tested in this session** (spawning agents was out of scope). If
  it works here it is the one primitive that would change the analysis — see
  §7.

---

## 4. Option A — cloud routine, one fire per stage

The only shape that works in the cloud, given that a session cannot spawn
sessions: **stop trying to move the loop, and make the loop external.**

```
stage PR merged  ──GitHub webhook──▶  routine fires
                                        │
                                 one cloud session
                                 /plan-run <next runnable stage>
                                 merges its own stage PR ──┐
                                                            │
                                        ◀───────────────────┘
```

A GitHub trigger on `pull_request.closed`, filtered to `is merged = true` and
head branch matching the stage-branch pattern, makes each merged stage fire the
next one. The ledger stays the only state, exactly as today — the driver's
re-scanning loop is replaced by the merge event, which is a *better* trigger
because it is the real completion signal rather than a process exit code.

**What survives:** one fresh session per stage (each fire is a session); ledger
as sole state; no laptop; the plan→main PR stays manual because nothing in the
chain merges into `main`.

**What is lost or must be rewritten:**

| Driver responsibility | Status under a routine |
|---|---|
| Per-stage `--model` / `--effort` | **Lost.** One model per routine. Workaround: one routine per weight class, and a `routine:` column in the stage index — a real `.plan/` contract change. |
| Session profile (`--allowedTools`, `--plugin-dir`, `--setting-sources`, budget) | **Lost/changed.** Routines run with no permission mode and everything the environment allows. The plugin must be reachable from the cloned repo, not `--plugin-dir`. |
| Retry cap → `BLOCKED.md` + commit | Must be re-implemented **as prose in the routine prompt**. A model instruction, not code. |
| `gate: human` stop | Works by accident and correctly: the prompt reads the index, refuses the stage, does not merge, so the chain simply halts. |
| Notify | Replace with a connector (Slack) or a `gh` comment. |
| Closeout | A second routine, or a branch in the same prompt when the last stage settles. |
| Protected-branch refusal | Must be re-asserted in the prompt; the cloud has no `PROTECTED_BRANCHES` constant. |
| Worktree-per-stage | **Meaningless.** One session, one clone, nothing parallel. PSR's fixed git model (README §3) is a local-machine model; a cloud variant would need its own documented model. |

**Other frictions:** the clone starts from the default branch, so the prompt must
check out `plan-<slug>` first; webhook caps could drop a fire on a busy plan and
the chain would silently stall; a failed run leaves no retry unless another
event arrives; and the routine acts as Carlos's GitHub identity with no
per-action gate.

**Verdict:** genuinely viable, genuinely different. It buys laptop-off operation
and costs the per-stage weight control and the deterministic retry logic. Worth
shipping as a **documented recipe alongside the driver**, not as a replacement.

---

## 5. Option B — local orchestrator on `claude --bg`

Replace `plan_driver.py` with a skill run by an interactive, remote-controlled
orchestrator session: read the ledger → `claude --bg --cwd <worktree> --model X
--effort Y "/plan-run N --unattended"` → `notify_when_idle` → re-read the ledger
→ repeat.

**What survives:** everything in §2. Fresh full session per stage, per-stage
model and effort, the whole session profile (they are still CLI flags),
`gate: human`, notify. And it adds something new: because the orchestrator is
interactive and remote-controlled, **`gate: human` stages and permission prompts
become answerable from the phone**, which is exactly the capability the question
was reaching for.

**What it costs:**

- **The loop stops being code.** Retry caps, the round cap, the exact
  `BLOCKED.md` format, the protected-branch refusal, "never merge into main" —
  all become instructions a model follows rather than code that cannot deviate.
  For a plugin whose selling point is *a persistent plan that must not drift*,
  that is a regression in the wrong place.
- **Worktree collision.** `--bg` sessions auto-isolate into
  `.claude/worktrees/`, while PSR mandates sibling `../<repo>-sN` worktrees.
  Needs `worktree.bgIsolation: "none"` or a documented reconciliation.
- **Still needs the computer on.** This removes Python, not the machine — and
  the machine was the more painful half of the original complaint.
- Token cost per round for ledger re-reads, on top of the stage sessions.

**Verdict:** technically the closest match, and the least worthwhile. It spends
real effort to delete a 1,128-line script that already works, and pays for it in
determinism.

---

## 6. Recommendation, by effort

**Tier 1 — do this, it is cheap and it is what was actually wanted (≈ half a session).**
Keep `plan_driver.py` untouched. Document two things in the README's unattended
section:

1. Run the driver from a `claude --remote-control` session (or just leave one
   attached to the same machine) so the run is visible from the desktop app and
   the phone, and permission prompts and `AskUserQuestion` dialogs can be
   answered remotely.
2. A `PLAN_DRIVER_NOTIFY` recipe that reaches the phone — the hook already
   exists and takes an arbitrary command.

Optionally, a Desktop scheduled task whose instruction is "run
`python scripts/plan_driver.py`" in the plan-branch folder. That fires the
existing driver nightly without a terminal, keeps every guarantee, and is about
five minutes of setup. It does not remove Python; it removes *remembering*.

**Tier 2 — worth building, ships as an addition (≈ 2–3 stages).**
A documented **cloud-routine recipe**: the routine prompt, the
`pull_request.closed` + merged + head-branch filter, the plan-branch checkout
step, and the `.plan/` contract changes it implies (how weight is chosen when
the routine owns the model, how a block is recorded without the driver). Land it
under `examples/` plus a README section titled honestly — *unattended without a
computer, with these trade-offs* — rather than presenting it as the new default.
Requires one real end-to-end plan run to trust it.

**Tier 3 — decline for now (≈ 5+ sessions, ongoing cost).**
Rewriting the driver as a `claude --bg` orchestrator skill. The payoff over
Tier 1 is small and the determinism loss is real.

---

## 7. Open questions worth ten minutes each

0. **Can a routine-run session fire the next routine? PROBED 2026-08-24: NO,
   on both available paths.** Two throwaway routines were created via
   `RemoteTrigger` (`trig_01K8XRzDyLsFb7gWPioJZ89c` target,
   `trig_01TUSkmjPQrbbPaSGYqAfua6` firer; both left disabled afterwards) and
   the firer was run twice:
   - **No tool path.** Inside the run session, no tool addresses a routine by
     id. The `Claude_Code_Remote` meta-connector listed in the trigger's
     `mcp_connections` metadata does **not** surface in the run — only the
     ordinary claude.ai connectors (Google Drive, Spotify) do. `CronCreate`
     etc. are session-local, in-memory, and cannot touch the `trig_...`
     namespace. Confirmed in an unrestricted second run
     (`cse_01UUPxeN22jLhe1XvJCCih7a`).
   - **No ambient credentials.** An unauthenticated `curl` POST to the
     `/routines/<id>/fire` endpoint from inside the run returned **401**
     (`cse_01XuqFjh7YQjWQwoWyR51vco`).
   - **Remaining sliver, untested:** `/fire` with a pre-provisioned bearer
     token stored in the environment's variables. Tokens are generated on the
     web UI only (shown once), so this needs a manual step per stage-routine.
     Mechanically it should work — the endpoint is plain HTTP + routine-scoped
     token — but it is unverified, and it means N tokens for N stages, managed
     by hand.
   - **Bonus finding:** the probe run *flagged the probe prompt as a
     prompt-injection attempt and refused the fire step it couldn't perform
     anyway*, pushing a mobile notification about it. A routine whose prompt
     asks the session to trigger other automation may meet the same
     resistance — a self-advancing chain fights the model's own guardrails,
     not just the credential model.

   **Also probed the CREATE path (2026-08-24, `cse_01L2xHhHjTyVKw1xLpnN44mf`),
   because the fire path was the wrong test for the chaining scenario.** The
   intended chain is: each stage's run session *creates the next stage's
   routine* (via the same `meta_mcp` path that made "Hello World"), scheduled a
   minute out. Result: **also NO.** Inside the routine-run session,
   `ListConnectors` returns only Google Drive and Spotify — the
   `Claude_Code_Remote` **meta-connector is absent from the worker**, even
   though it is listed in the routine's `mcp_connections` metadata. `ToolSearch`
   across `create routine` / `create_trigger` / `RemoteTrigger` /
   `schedule cloud agent` returns only `CronCreate`/`CronList`/`CronDelete`,
   whose own schema says *"durable persistence is not available … session-only,
   in-memory, gone when this session ends."* There is no durable-routine
   creation tool in the worker at all.

   **Independently reproduced 2026-08-24** by a second, unrelated session on a
   different surface (which had `mcp__Claude_Code_Remote__*` rather than
   `RemoteTrigger`), using its own freshly-created probe routines. Its run
   (`cse_011yby4yrUy7FRx1a1GH1nM9`) ended with the verdict line
   `PROBE-RESULT: fire=failed:no_tool_available create=worked:session_only_not_durable`
   — matching this note's finding on both paths: `ListConnectors` showed only
   Google Drive and Spotify, `ToolSearch "create_trigger"` returned *no
   matching deferred tools*, and the unauthenticated `/fire` curl returned
   **401** again.

   **The trap in that run, worth recording:** it called `CronCreate` with
   `durable: true`, got back a job, and a minute later the same session printed
   `CHAIN-CHILD-ALIVE`. That looks like a successful chain and is not one —
   `CronCreate`'s own schema says `durable` *"has no effect … all jobs are
   session-only (in-memory, gone when this Claude session ends)"*. The child
   fired **inside the same session**, as a queued prompt, not as a new cloud
   session. A chain built on it dies with the session and cannot span stages.
   Confirmed externally: no `PROBE child` routine appeared in `list_triggers`.

   **Root cause, stated plainly:** the routine tooling (`create_trigger` /
   `RemoteTrigger`, carried by the `Claude Code Remote` meta-MCP) lives on
   **user-credentialed surfaces** — the local CLI session, the desktop app, the
   phone. That is why "Hello World" (created from the phone) and these probe
   routines (created from this local CLI session via `RemoteTrigger`) worked.
   The **cloud routine-run worker does not carry that meta-MCP**, by design, so
   a running routine can neither fire nor create another routine. The asymmetry
   is credentials + tool surface, not a missing feature.

   **Consequence:** the self-advancing chain — a run session creating or firing
   the next stage — is out (short of the manual-token `/fire` variant, which
   needs N web-generated tokens by hand). What remains is **external
   orchestration by a user-credentialed surface**:
   - **Local orchestrator** (a `claude` session, or `plan_driver.py` gaining a
     `RemoteTrigger`-equivalent call): keeps the deterministic loop and
     per-stage model, fires one routine per stage into the cloud. Needs the
     machine/session alive, but the *stage work* runs in the cloud and is
     answerable from the phone. This is the strongest hybrid and was not among
     the original three options.
   - **GitHub webhook** on stage-PR merge fires the next stage's routine — no
     creation inside the run, the merge event is the trigger. Fully laptop-off,
     but per-stage model means one pre-created routine per stage and the chain
     stalls silently if a webhook is dropped or a stage doesn't merge.
   - **Pre-create all N stage routines up front** from the phone/local session,
     each with its own model — but they still need *something* to fire the next
     in order, so this still reduces to one of the two above for the trigger.
1. **`Agent(isolation: "remote")`** — is it enabled on this account? If a local
   session can fan stages out to cloud sandboxes *as separate agents*, the
   cloud option stops being "one session per fire" and starts looking like the
   driver with the machine removed.
2. **Can a routine push `plan-<slug>-sN` and merge its own stage PR?** The
   branch rules say non-`claude/` branches are allowed when unprotected, no
   other open PR, no foreign commits — stage branches should qualify, but this
   is worth proving before designing around it.
3. **What are the actual webhook caps?** Shown at `claude.ai/code/routines`. A
   plan with many small stages could hit them and stall silently.
4. **Does the plugin load in a cloud session? PROBED 2026-08-24: NOT BY
   DEFAULT — and this is the design's real blocker.**
   - **Plain routine run: no plugin skills.** Two runs
     (`cse_011xBCD2odNZtNaQhBnDfuw2`, `cse_01YbZXmQHTHeoDWEdmR4EtJJ`) both
     reported `plan-run=no summary=no`. The visible skill list was the stock
     Anthropic set only — no `plan-staged-rollout:*`, no `carlos:*`. So
     `/plan-run` does not exist in a routine run out of the box.
   - **`enabled_plugins` is a real top-level field on the trigger, and it is
     server-validated.** Probing its schema: it is a **string array** (a
     non-string 400s with `invalid value for string field enabled_plugins`),
     but plausible names (`plan-staged-rollout`, `carlos`,
     `plan-staged-rollout@by-carlos`) are **accepted with 200 and stored as
     `[]`** — validated against something and dropped when unresolved. So a
     supported mechanism exists; the identifier format is undocumented and not
     guessable from the API. Set it from the web routine form or `/schedule`,
     which resolve against actually-installed plugins, then read the stored
     value back with `action:get` to learn the format.
   - **`extra_marketplaces` schema, partially mapped:**
     `[{name: <string, required>, source: <object, required>}]`. `source` as a
     bare string 400s (`unexpected token`); as an object it is accepted but
     tolerates unknown keys and silently drops the entry when it doesn't
     resolve. Shape of `source` not established — stop guessing, read it back
     from a UI-created routine.
   - **Confound worth noting:** the probe routines had **no repository
     attached** (`env[info]: No sources configured`). They therefore tested
     *plugin* availability only, not repo-committed skills.
   - **The workaround that needs no undocumented API:** the routines doc states
     a run can use **skills committed to the cloned repository**. So vendor a
     minimal stage-runner skill into the target repo's `.claude/skills/` on the
     plan branch — `plan-stages` already commits the `.plan/` scaffold there
     and can write the skill in the same commit. That makes the cloud design
     independent of plugin loading entirely, and is the recommended path until
     the `enabled_plugins` format is known. Untested, but documented.

---

## Sources

- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)
- [Routines](https://code.claude.com/docs/en/routines)
- [Cloud environments](https://code.claude.com/docs/en/cloud-environments)
- [Desktop scheduled tasks](https://code.claude.com/docs/en/desktop-scheduled-tasks)
- [Cross-session messaging](https://code.claude.com/docs/en/cross-session-messaging)
- [Remote Control](https://code.claude.com/docs/en/remote-control)
- [Agent view / background agents](https://code.claude.com/docs/en/agent-view)
- [Introducing routines in Claude Code](https://claude.com/blog/introducing-routines-in-claude-code)
