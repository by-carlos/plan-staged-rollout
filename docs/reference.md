# Reference

## Per-stage knobs

Each stage declares its own weight, so you don't pay heavy process on trivial
work — and don't skimp on the hard parts:

| Flag | Values | Meaning |
|---|---|---|
| `depends` | stage id(s) or `—` | prerequisites that must be `done` or `skipped` first |
| `mode` | `direct` \| `brainstorm` | whether the stage needs a design pass first |
| `exec` | `inline` \| `subagent(<model>)` | where the implementation churn lives |
| `model` / `effort` | launch hints | recommended session weight; checked, not faked |
| `gate` | `auto` \| `human` \| `local` | may the stage be launched with nobody watching? `human` means never — a person's judgment or presence is part of the stage; `local` means never *by a driver running elsewhere* — the stage needs a resource only the local machine has. An unattended runner stops in front of either |

And two flags for the plan as a whole, on the **plan flags** line under the
stage index:

| Flag | Values | Meaning |
|---|---|---|
| `merge` | `manual` \| `auto` | under `auto` the session squash-merges its own stage PR into the plan branch once checks are green, instead of offering it; stage PRs only — the plan→main PR is manual in every mode |
| `plan-dir` | `delete` \| `keep` | what closeout does with `.plan/`: remove it as the last commit on the plan branch, or leave it in place for a plan that doubles as documentation |

These two are the plan's **declared defaults** — the answers a session applies
when there is nobody to ask. An interactive session still puts each one to
you, with the declared value as its recommendation; `--unattended` is what
selects the default over the question. The full classification of which
questions have a default and which are hard stops in every mode is in the
skill (*Unattended mode*).

Defaults stay cheap where cheap is safe, and reproduce the fully-manual flow: `direct`,
`inline`, a model sized to finish the stage, `gate: auto`, `merge: manual`,
`plan-dir: delete` — a plan that predates these flags needs no edit. Escalate
only where a stage has genuine open design questions (`brainstorm`, which also
makes it `gate: human`), needs a resource only the local machine has
(`gate: local`), or has heavy iteration churn (`subagent`); opt into
`merge: auto` only for a plan you intend to run unattended.

### Why `model` / `effort` are hints, not automation

Launching a *local* stage at its recommended weight is **manual by design,
because the platform gives no other option.** Nothing available to a Claude
Code session can start another local top-level session at a chosen model or
effort level:

- an agent cannot switch its own model mid-session, so a stage that opens on
  the wrong model can only report the mismatch, not correct it;
- effort **is** readable, from `CLAUDE_EFFORT` in the environment, so the
  protocol verifies it rather than merely reminding — but a session still
  cannot *change* it, so a mismatch is reported, never corrected;
- the desktop app's suggestion chips, which a finished stage
  [now offers](staged-rollout.md#starting-the-next-stage-from-a-chip-desktop-app), carry either
  only a title, a prompt and a working directory (`spawn_task`) or a model and
  effort that may only go *down* from the finishing session's (`start_session`)
  — so a chip-started session inherits the finishing session's model and
  effort rather than reliably getting the stage's recommendation. Chips are
  also app-only; they don't exist in the CLI or on a phone.

Hence the split the protocol actually uses: **verify the model** (readable from
the session), **remind about effort** (not readable), and hand the human the
exact command plus its recommended weight at every handoff. `.plan/` stays the
carrier of that recommendation because it is the only channel that survives
across sessions and works everywhere the plugin does.

The remote path is the partial exception:
[a fired cloud stage](ON-THE-RUN.md#under-the-hood) has its
`model` booked from the stage index at fire time — that booking is measured to
take effect — while booking `effort` remotely is still an open question (#125),
so the effort column stays a reminder the stage prompt restates in every mode.

## The ledger, kept slim

The ledger is read by *every* stage session, so its size taxes every future
session. It is therefore split:

- a **status table** — strictly one line per stage
  (`Stage | Status | Verified | Date | Result`), machine-greppable, so
  "what's the next runnable stage" is trivial for you and the agent;
- a **notes section** — one block per stage for as-built detail, acceptance
  evidence, gotchas, and handoff notes. Sessions read only the blocks of the
  stages they depend on.

This split came directly from field experience: in the pilot rollout the
detailed notes lived inside table cells, and by stage 5 a single row had grown
to ~500 words that every subsequent session re-read. The method's token
promise only holds if the ledger stays on a diet.
