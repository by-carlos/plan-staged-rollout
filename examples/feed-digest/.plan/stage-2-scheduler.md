# S2 — Scheduler and runbook

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.

## Goal

Run the job every morning on the home server without anyone watching, and
write down what to do when the digest does not arrive. This stage needs the
server, which is only reachable from the local network.

## Steps

- [x] `deploy/feed-digest.service`: a oneshot unit running `feed-digest run`,
  with `EnvironmentFile=/etc/feed-digest/env` for the webhook URL (D-3).
- [x] `deploy/feed-digest.timer`: daily at 07:00 local, `Persistent=true` so a
  run missed while the server was off happens at boot (D-5).
- [x] Install both on the server and enable the timer.
- [x] `RUNBOOK.md`: "the digest did not arrive" — read the journal, rerun by
  hand (safe, D-4), rotate the webhook if it leaked.

## Acceptance

- `systemctl list-timers feed-digest.timer` on the server shows the next run.
- `systemctl start feed-digest.service` posts once; starting it again posts
  nothing new, and `journalctl -u feed-digest` shows both runs.
- `RUNBOOK.md` has a section for each failure the journal can show.

## Artifacts

`deploy/feed-digest.service`, `deploy/feed-digest.timer`, `RUNBOOK.md`.
Server-only, never committed: `/etc/feed-digest/env` (holds the webhook URL).
