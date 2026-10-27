# 0001. Deduplicate entries by a stable key in a SQLite state file

Date: 2026-09-18
Replaces: none

## Context

The digest must never post an entry twice, including when a run is repeated
by hand or killed halfway. Feeds are irregular: several we follow give no
`id` for their entries, and some re-date old entries when they are edited.
Whatever records "already posted" has to survive a crash mid-write and
answer quickly for a few thousand entries.

## Decision

Each entry gets a key: the feed's `id` when present, otherwise a SHA-256 of
its link and title. Posted keys live in a SQLite file (`state.db`) beside the
job. A run records its entries in one transaction, and only after the webhook
answers 2xx — so a failed or interrupted run leaves the state as it was, and
the next run posts the same entries again exactly once.

## Alternatives

- **A JSON file of posted keys** — simplest to read, but no atomic update: a
  run killed mid-write can corrupt it or lose the last run's keys.
- **A time window ("posted in the last 24 hours")** — no state at all, but
  late-dated and re-dated entries are missed or repeated.
- **The feed's `id` alone** — breaks on the feeds that omit it.

## Consequences

Reruns are safe, which is what lets scheduling skip a retry loop. The state
file is now part of the deployment: deleting it reposts everything still in
the feeds, and moving the job to another machine means moving `state.db`
too. Changing the key formula later needs a one-off migration of the stored
keys.
