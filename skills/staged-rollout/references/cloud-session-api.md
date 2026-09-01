# Cloud session creation — the recorded API shape

`scripts/cloud_fire.py` fires one stage as a cloud session by creating one
against `POST /v1/sessions`. **That endpoint is beta: its shape is measured,
not documented, and it can change without notice.** This file is the record
those measurements produced. When a fire starts failing, fix
[`build_payload`](../../../scripts/cloud_fire.py) against this record and
**re-measure against the live API** — never guess at a replacement shape — then
update this file with what you measured and when.

## Why not `claude --cloud`

The CLI's own cloud launcher cannot be scripted:

- It **requires a real TTY**. It errors under `--print`, under a pipe, and
  under pty emulation, so nothing a driver invokes through a shell can use it.
- It **silently drops `--effort`** behind a server-side feature gate: it books
  the model and nothing else. That is precisely the silent wrong-weight run the
  stage index's `effort` column exists to prevent — a stage would look fired at
  its recommended weight and not be.

The API underneath accepts both and echoes them back, so a wrong booking fails
loudly instead of running quietly at the wrong weight — which is why the script
uses it directly. Note the difference between *stored* and *in effect*: the
model booking is confirmed to take effect inside the container, the effort level
currently is not (see below).

## Create

```
POST https://api.anthropic.com/v1/sessions
```

Headers:

| Header | Value |
|---|---|
| `authorization` | `Bearer <access token>` |
| `anthropic-version` | `2023-06-01` |
| `anthropic-beta` | `ccr-byoc-2025-07-29` |
| `anthropic-client-platform` | `claude_code_cli` |
| `x-organization-uuid` | the account's organization UUID |
| `content-type` | `application/json` |

Body — the shape the CLI logs for its own launch (`--debug-file`, "Creating
session with payload:"), re-sent with `effort_level` added:

```json
{
  "title": "<session title>",
  "events": [
    {
      "type": "event",
      "data": {
        "uuid": "<uuid>",
        "session_id": "<uuid>",
        "type": "user",
        "parent_tool_use_id": null,
        "message": { "role": "user", "content": "<the instruction the session starts with>" }
      }
    }
  ],
  "session_context": {
    "sources": [
      {
        "type": "git_repository",
        "url": "https://github.com/<owner>/<repo>",
        "revision": "<branch the container checks out>"
      }
    ],
    "outcomes": [
      {
        "type": "git_repository",
        "git_info": {
          "type": "github",
          "repo": "<owner>/<repo>",
          "branches": ["<branch the session may push>"]
        }
      }
    ],
    "model": "claude-sonnet-5",
    "effort_level": "low"
  },
  "environment_id": "env_…"
}
```

Three things are easy to get wrong:

- **The prompt is a top-level `events` entry, not a `session_context` field.**
  It rides as a user-message event.
- **`environment_id` is required.** Omitting it returns `400
  invalid_request_error` with the bare message "The request was invalid" and no
  field named — so the failure reads as a payload problem rather than a missing
  argument. Environments are **account-level, not per-repo**, so the script
  discovers one from `GET /v1/sessions?limit=1` when `--environment-id` is not
  given, and that works even for a repo that has never had a session.
- **The event's `uuid` and `session_id` are generated fresh.** The CLI redacted
  its own values in its log, so whether the server validates them is unmeasured;
  freshly generated UUIDs are accepted.

A `200` echoes the stored `session_context` back with the session `id`
(`session_…`), `session_status: "pending"`, and an `mcp_config` the platform
injects — a per-session GitHub MCP proxy, because cloud containers have no `gh`
binary and GitHub access goes through that server.

## Read back

| Call | Returns |
|---|---|
| `GET /v1/sessions/<id>` | the session record — status, stored context |
| `GET /v1/sessions/<id>/events` | the transcript, readable while it runs and after it ends |

Same headers. `cloud_fire.py --tail <id>` calls both. This is the only honest
way to confirm a booking took effect: the create response echoes what the server
*stored*, and the transcript shows what the container actually got.

## What the runtime honours (measured)

- **`model` is booked** — the container's CLI runs with `--model <value>` and
  the session self-reports it.
- **`effort_level` is stored, and there is currently no way to confirm it takes
  effect.** The create response echoes it back, so the API accepts and persists
  it — `cloud_fire.py` fails a fire whose echo disagrees. Whether the container
  actually runs at that level is a separate question, and as of 1 Sep 2026 it
  cannot be answered from inside: `CLAUDE_EFFORT`, the variable that used to
  report it, is **empty at every level**. Measured with one session per value,
  all `claude-haiku-4-5`, all running a bare `echo` and stopping:

  | Booked `effort_level` | `CLAUDE_EFFORT` | `CLAUDE_CODE_EFFORT_LEVEL` |
  |---|---|---|
  | `low` | empty | empty |
  | `medium` | empty | empty |
  | `high` | empty | empty |

  This **supersedes** the 25 Aug 2026 measurement, which recorded a session
  booked at `low` reporting `CLAUDE_EFFORT=low`. Something changed between the
  two dates; the readout is gone. Two explanations fit and nothing available
  from outside separates them — the container may still honour the booking and
  merely stopped exporting the variable, or the booking may no longer be
  applied. Until a new readout appears, treat a booked effort level as
  **requested, not proven**, and do not write a claim anywhere that says
  otherwise. `CLAUDE_CODE_EFFORT_LEVEL` is an input override, not a readout, and
  was empty throughout in both rounds.

  Values above `high` (the CLI's `xhigh`, `max`) have no measured API equivalent
  at all — `cloud_fire.py` books `high` for them and says so rather than
  dropping them silently.
- **The container does not start on `sources.revision` by name.** It starts on a
  branch the platform creates, named after the first entry of
  `outcomes.branches` with a random suffix (`…-s0-wcssqj`), whose *content* is
  `sources.revision`. Measured 1 Sep 2026: a fire booking
  `sources.revision: plan-cloud-fire-probe` and
  `outcomes.branches: [plan-cloud-fire-probe-s0, plan-cloud-fire-probe]` began
  with `git rev-parse --abbrev-ref HEAD` reporting
  `plan-cloud-fire-probe-s0-wcssqj`, with `.plan/` present and correct. Pushing
  that suffixed branch **was** permitted even though its literal name is not in
  `outcomes.branches`, so the listed value behaves as a base name rather than an
  exact match. For a staged rollout this reads as branch drift — `PLAN.md`'s
  preflight requires the clone's HEAD to be the plan branch — so
  `cloud_fire.py`'s prompt warns the session up front that the drift is expected
  and correctable rather than a fault.
- **Plugins do not load in cloud containers** — marketplace loading is disabled
  by environment flag before settings are read. A fired session therefore cannot
  invoke `/plan-staged-rollout:plan-run`, and does not need to: `.plan/PLAN.md`
  carries the whole operating protocol, so `cloud_fire.py` sends the standalone
  prompt that file was designed for.

## Credentials

The bearer token is **not** the `gh` credential, and a driver needs a token that
refreshes rather than a one-time probe. `cloud_fire.py` resolves, first hit
wins:

1. `CLAUDE_CODE_OAUTH_TOKEN` from the environment — the CLI's own override,
   honoured so CI or a one-off shell can inject a credential.
2. A self-renewing OAuth grant file (`~/.claude/.batch-oauth-token.json` by
   default, `$PLAN_CLOUD_TOKEN_FILE` to move it), seeded once per machine with
   `--seed-token` and **renewed by the script itself** when the stored access
   token is lapsed or nearly so. This is the source an unattended run is meant
   to use.
3. `~/.claude/.credentials.json` — the CLI's own short-lived (8h) access token.
   Last resort, and routinely lapsed: where sessions are desktop-hosted the host
   app refreshes OAuth in memory and nothing maintains the on-disk file.

The organization UUID comes from `.oauthAccount.organizationUuid` in
`~/.claude.json`.

Two facts worth not re-deriving:

- **`claude setup-token` credentials do not work here.** The long-lived
  `sk-ant-oat01-…` credential is accepted by inference endpoints
  (`GET /v1/models` → 200) but lacks the `user:sessions:claude_code` scope, and
  `/v1/sessions` refuses it with `401 Authentication failed` under every header
  combination tried.
- **The refresh flow** is `POST https://platform.claude.com/v1/oauth/token` with
  `{grant_type: "refresh_token", refresh_token, client_id}` — endpoint and
  public client id both read out of the installed Claude Code binary. Send a
  real `user-agent`: Cloudflare refuses Python's default signature outright
  (403, error 1010). A `200` returns a **rotated** pair with `expires_in` 28800
  (8h), the full scope set including `user:sessions:claude_code`, and
  `refresh_token_expires_in` of roughly 26 days, renewed on every use.

Rotation has one consequence worth stating plainly: every refresh invalidates
the previous refresh token, so the pair in the grant file is the only live copy
of that chain. Two grant files forked from one login will kill each other at the
first renewal — which is why the default path is shared rather than
plugin-private, and why concurrent fires must not race a refresh. A chain left
idle past its refresh window dies and needs re-seeding.

A `401` on a credential that passed `--probe-credentials` is a genuine auth or
scope failure, not payload drift.

## Provenance

The mechanism was proven before it was vendored here: batch-orchestration
tooling in a separate repository fires cloud sessions through this same
endpoint, and fired six in one batch on 31 Aug 2026 with model and effort booked
per session. The measurements above were taken between 25 and 31 Aug 2026
against Claude Code 2.1.240. Re-measure rather than trust them if the endpoint
starts behaving differently.
