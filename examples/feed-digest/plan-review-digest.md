# Plan review digest — feed-digest, 2026-09-14

<!-- In a real plan this file is scratch: it lives in the bootstrap session's
scratchpad and is never committed. It is kept here so you can see what the
main thread reads. The "Outcome" lines were added once the outcomes were
applied; PLAN.md › Plan review is the durable record. -->

Lenses: Simplicity (always) · Security (secret, network, dependency) ·
Operator (daily timer). Architect off: one component, no shared interface.

- **Where:** PLAN.md › Frozen decisions (webhook key in `feeds.toml`)  *(Security)*
  **Problem:** `feeds.toml` is committed, so the webhook URL would be in git history.
  **Change:** add a decision: the URL comes only from `FEED_DIGEST_WEBHOOK`; S1 reads it, S2's unit loads it.
  **Outcome:** change the plan — new D-3; S1 and S2 steps edited.
- **Where:** stage-2-scheduler.md › Steps, step 3 (retry loop)  *(Simplicity, Operator)*
  **Problem:** a retry loop repeats what the next day's run does, and adds a process to watch.
  **Change:** cut the step; D-5 says "no retry loop", relying on D-4's safe reruns.
  **Outcome:** change the plan — step cut, D-5 reworded.
- **Where:** stage-0-fetch-and-state.md › Steps, step 2  *(Security, Operator)*
  **Problem:** no timeout or size cap: one stalled or huge feed hangs the run.
  **Change:** 20-second timeout and 5 MB cap per feed; a failing feed is skipped by name.
  **Outcome:** change the plan — S0 step 2 edited.
- **Where:** stage-2-scheduler.md › Acceptance  *(Operator)*
  **Problem:** if the timer stops firing, nothing fails, so nobody is told.
  **Change:** add an external heartbeat check that alerts when no digest arrived by 08:00.
  **Outcome:** file a follow-up — #41; a monitoring service is outside this plan.
- **Where:** PLAN.md › Frozen decisions › D-4  *(Simplicity)*
  **Problem:** SQLite may be heavier than a JSON file of posted keys.
  **Change:** store posted keys in `state.json`.
  **Outcome:** accept with a reason — `sqlite3` is standard library and gives the atomic update D-4 needs.
