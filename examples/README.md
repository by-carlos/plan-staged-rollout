# Examples

Worked examples of the artifacts a staged rollout produces and runs on. The
templates in
[`skills/staged-rollout/references/templates/`](../skills/staged-rollout/references/templates/)
show the *shape* of a scaffold; these show what good **filled-in** content
looks like, so you can judge your own `.plan/` without having to run
`/plan-stages` on a real project first.

## [`uptime-page/`](uptime-page/) — a scaffolded `.plan/`, captured mid-flight

A complete `.plan/` for a toy project — a tiny Python tool that checks a list
of URLs and publishes a static HTML status page — frozen at a realistic
mid-rollout moment:

| Stage | State shown |
|---|---|
| S0 Checker core | `done` — real acceptance output pasted as evidence, plus an as-built note and a gotcha |
| S1 CLI runner | `doing` — stopped mid-stage: completed steps ticked, handoff note in the ledger |
| S2 Status page | `todo` — untouched, exactly as scaffolded |
| SF Plan review | `todo` — the standing final review every plan gets |

### What to notice

The discipline the [plugin README](../README.md) describes, in practice:

- **Ledger rows stay one line.** The status table in
  [`LEDGER.md`](uptime-page/.plan/LEDGER.md) is a 4-line glance; every detail —
  evidence, gotchas, the handoff — lives in the per-stage notes blocks below
  it. The table is re-read by *every* future session, so its size taxes all of
  them; the notes blocks are read only by the stages that depend on them.
- **`done` means evidence, not assertion.** S0's notes block contains the
  actual terminal output of its acceptance checks, pasted — not a claim that
  they passed — followed by the as-built summary and the one gotcha the next
  stages need to know.
- **`doing` is a normal, resumable state.** S1's stage file
  ([`stage-1-cli.md`](uptime-page/.plan/stage-1-cli.md)) has its completed
  steps ticked, and its ledger notes say exactly what is left and where to
  resume. A fresh session picks up from the first unticked box.
- **Flags live only in the PLAN.md stage index.** No stage file restates its
  `depends` / `mode` / `exec` / `model` / `effort` / `gate` — a copy is what drifts.
  The [`PLAN.md`](uptime-page/.plan/PLAN.md) index is the single authoritative
  home the tooling reads.
- **Decisions live only in Frozen decisions.** Stage files and ledger notes
  *point at* `PLAN.md` (see S1's handoff referencing S0's no-raise contract);
  nothing restates a choice.
- **Defaults stay cheap.** Every stage here is `direct` / `inline`, and only
  the keystone (S0) recommends the top-tier model. Escalate a flag only where
  a stage genuinely warrants it.

### Two honest caveats

- At three implementation stages, this toy sits *below* the ~four-session
  floor where the scaffold pays off — it is sized for readability, not as a
  sizing recommendation. See "When NOT to use it" in the skill.
- The example is inert where it lives: the plugin's SessionStart hook only
  reacts to a `.plan/` at the repo **root**, so this nested copy never nudges
  your sessions.

## [`feed-digest/`](feed-digest/) — the planning and closing artifacts, at closeout

A second toy project — a daily job that posts new RSS entries to a team chat
channel — frozen at the moment every stage is `done` and `/plan-close` is
next. Where `uptime-page/` shows a plan being *run*, this one shows what
bootstrap writes before stage 1 and what the final review leaves behind once
`.plan/` is gone. Only the plan and the decision record are included; the
job's code and its own README are not.

| What | Where to look |
|---|---|
| Requirements, confirmed before any decision | [`.plan/PLAN.md`](feed-digest/.plan/PLAN.md) › Requirements |
| Decision triage groups — **Decided**, **Needs you**, **Default for now** | [`.plan/PLAN.md`](feed-digest/.plan/PLAN.md) › Frozen decisions, D-1 to D-7 |
| The brief: stamp line, Mermaid day-to-day flow, stage map | [`.plan/BRIEF.md`](feed-digest/.plan/BRIEF.md) |
| The plan-review digest, each finding with its outcome | [`plan-review-digest.md`](feed-digest/plan-review-digest.md), recorded in [`.plan/PLAN.md`](feed-digest/.plan/PLAN.md) › Plan review |
| Close-time triage: three decisions dropped, three entries, one ADR | [`.plan/LEDGER.md`](feed-digest/.plan/LEDGER.md) › SF › Kept decisions, [`DECISIONS.md`](feed-digest/DECISIONS.md), [`docs/adr/0001-dedupe-by-stable-entry-key.md`](feed-digest/docs/adr/0001-dedupe-by-stable-entry-key.md) |
| The pointer line, in the agent instructions file | [`AGENTS.md`](feed-digest/AGENTS.md) — `AGENTS.md`, not `CLAUDE.md`, so Claude Code does not load the toy's instructions while you work in this repository |

### What to notice

- **Requirements come before decisions.** The ranked constraints are what the
  decisions answer to: D-3 exists because constraint 2 makes the webhook URL
  a secret.
- **The brief is generated, never written.** Line 1 of `BRIEF.md` carries the
  first 12 hex characters of `git hash-object .plan/PLAN.md`, and every
  section names the `PLAN.md` section it came from. Run the command on this
  example's `PLAN.md` and the hash matches.
- **Every review finding has a location, a change and one outcome.** Three
  changed the plan, one became follow-up #41, one was accepted with a reason.
  Lenses turn on from triggers: Architect stayed off, and the brief says why.
  The digest itself is scratch in a real plan; it is kept here only to show
  what the main thread reads.
- **Most decisions are dropped at close.** Of seven, three are dropped (the
  code or the plan's end makes them plain), three become `DECISIONS.md`
  entries, and one — hard to reverse, with real alternatives — becomes an ADR
  that its entry links to. The `#### Kept decisions` heading is the exact form
  `/plan-close` copies into the final PR body.
- **`gate: local` in passing.** S2 needs the home server, reachable only from
  the local network, so its stage index row says `local` and the stage map
  marks it.

All numbers (#3, #5, #41) and hosts are invented.

## [`on-the-run/`](on-the-run/) — driving a plan on the cloud

The current design fires each stage as a Claude Code cloud session straight
from `/plan-run`, through the built-in `RemoteTrigger` tool — no hand-set-up
routine, no separate prompt to paste anywhere. `/plan-run` itself creates a
short-lived, run-once routine per stage under the hood as the vehicle for
firing it; that's an implementation detail of the tool, not a setup step for
a person. See [`docs/ON-THE-RUN.md`](../docs/ON-THE-RUN.md) for the
quickstart and
[`remote-driver.md`](../skills/staged-rollout/references/remote-driver.md)
for the full mechanism.

- **[`stage-runner-prompt.md`](on-the-run/stage-runner-prompt.md)** and
  **[`orchestrator-prompt.md`](on-the-run/orchestrator-prompt.md)** are
  **retired** (#127) — they were the pasted prompts for the earlier,
  hand-provisioned-routine design. Kept only so old links keep resolving; see
  each file for what replaced it.
- **[`poc/`](on-the-run/poc/)** — the inputs for the end-to-end proof of
  concept that validated the earlier design: a four-stage plan for a
  throwaway repository (two automatic stages, one `gate: human` stage, and a
  closeout), plus `verify_run.py`, which makes the run's pass/fail a command
  result rather than a transcript to read.

## [`tickets/`](tickets/) — a custom ticket template and the draft it produces

The examples above are about plans. This one covers the ticket skills
(`create-issue` and `work-issue`, see [Tickets](../docs/tickets.md)): a small
team template and one filled draft written against it.

| File | What it is |
|---|---|
| [`my-team.toml`](tickets/my-team.toml) | A GitHub team template in the format [Customizing the ticket template](../docs/ticket-templates.md) documents. It extends the built-in default and states only what differs: 60-character titles, task types without Story, three priorities, and one extra optional section, "Rollout notes". |
| [`draft.json`](tickets/draft.json) | A draft of the kind `create-issue` produces after its floor test and drafting step, for a made-up bug in a made-up repo. Its sections match the template. |
| [`body.md`](tickets/body.md) | The ticket body exactly as `create-issue` renders it from the draft, which is what would be posted. |

### Check it yourself

From the repository root, with Python 3.11 or later (use `python` for
`python3` on Windows):

```bash
python3 tickets/scripts/ticket_template.py validate examples/tickets/my-team.toml --tracker github
```

That is the loader the skills use, and it prints `OK` with the template chain.
To see the rest, resolve the template into a file and run the draft through
the same checks `create-issue` runs:

```bash
python3 tickets/scripts/ticket_template.py resolve --tracker github --template examples/tickets/my-team.toml > resolved.json
python3 tickets/scripts/ticket_core.py check --template resolved.json examples/tickets/draft.json
python3 tickets/scripts/ticket_core.py render --template resolved.json examples/tickets/draft.json
```

`check` prints `"ok": true` with no errors or warnings, and `render` prints
`body.md`. Nothing here touches GitHub: posting is a separate step, and only
after you approve it.

### What to notice

- **A template states only the difference.** `extends = "default"` keeps
  everything not mentioned. Arrays replace rather than merge, so adding one
  section means restating the whole `body.sections` list.
- **Priorities follow the tracker.** The `[per_tracker.github.priority]` table
  swaps the scale for GitHub only; a Jira run of the same template would keep
  the default's.
- **The draft carries its own notes.** `draft_notes.read` records what the
  drafter looked at, which is what lets the size and effort proposals be set
  instead of left blank. The notes are never posted.
- **All names are placeholders.** The repository, the bug and the label are
  invented; nothing in this folder refers to a real project.
