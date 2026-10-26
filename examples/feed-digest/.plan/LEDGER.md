# feed-digest — build ledger

Statuses: `todo → doing → done`, plus `blocked` (waiting on a human or an
external gate — the stage becomes a runbook) and `skipped` (decided against,
one-line reason). Partial completion is a normal, resumable state.

Keep table rows to **ONE line** — detail goes in the notes block below, never
in a table cell. Sessions read the status table plus only the notes blocks of
the stages they `depend` on (the final review stage reads all of it). Update
your stage's row and notes block at the end of every session (Operating
protocol, finish protocol).

## Status

| Stage | Status | Verified | Date | Result |
|---|---|---|---|---|
| S0 Fetch and state (keystone) | done | yes | 2026-09-15 | Fetch, SQLite state, dry-run CLI; 14 tests pass |
| S1 Render and post | done | yes | 2026-09-16 | Digest + webhook post; D-6 cap kept; 22 tests pass |
| S2 Scheduler and runbook | done | yes | 2026-09-16 | Timer enabled on the server; RUNBOOK written |
| SF Plan review | done | yes | 2026-09-18 | No new stages; 7 decisions triaged; cold reader clean |

## Notes

As-built notes, acceptance evidence, gotchas, handoff notes, follow-ups. One
block per stage; sessions read only the blocks of their `depends` stages.

### S0 Fetch and state (keystone)

**Acceptance evidence** (2026-09-15, stage worktree):

```
$ pytest -q
..............                                                   [100%]
14 passed in 0.41s

$ feed-digest run --dry-run --feeds tests/fixtures/feeds.toml
release-notes: 3 new
team-blog: 2 new
slow-feed: skipped (timed out after 20s)
5 new entries

$ feed-digest run --dry-run --feeds tests/fixtures/feeds.toml   # after mark_posted
no new entries
```

**As built:** `new_entries()` returns entries oldest first; `mark_posted()`
takes the list back and writes it in one transaction.

**Gotcha for S1:** `--dry-run` never calls `mark_posted()`, so the second
dry run above was made after calling it from the test helper. S1's real
`run` must call it only after the post succeeds (D-4).

### S1 Render and post

**Acceptance evidence** (2026-09-16, stage worktree):

```
$ pytest -q
......................                                           [100%]
22 passed in 0.58s

$ feed-digest run --dry-run --feeds tests/fixtures/feeds.toml
*Feed digest — 5 new*
release-notes
• v2.4 is out — https://example.org/releases/2.4
• v2.3.1 security fix — https://example.org/releases/2.3.1
• Roadmap for Q4 — https://example.org/roadmap
team-blog
• Moving the build to containers — https://blog.example.org/containers
• What we learned from the outage — https://blog.example.org/outage

$ env -u FEED_DIGEST_WEBHOOK feed-digest run; echo "exit $?"
FEED_DIGEST_WEBHOOK is not set; nothing posted.
exit 2
```

**D-6 revisited:** the busiest fixture day has 26 entries; 30 stays, and
PLAN.md › D-6 now records it (brief regenerated in the same commit).

### S2 Scheduler and runbook

Ran on the laptop on the home network (`gate: local` — the server is not
reachable from a cloud session).

**Acceptance evidence** (2026-09-16):

```
$ ssh <server> systemctl list-timers feed-digest.timer
NEXT                        LEFT     LAST  PASSED  UNIT               ACTIVATES
Thu 2026-09-17 07:00:00 CEST 14h left -     -       feed-digest.timer  feed-digest.service

$ ssh <server> 'sudo systemctl start feed-digest.service; sudo systemctl start feed-digest.service; journalctl -u feed-digest -n 4 -o cat'
5 new entries; digest posted
Finished feed-digest.service.
no new entries
Finished feed-digest.service.
```

**Not committed:** `/etc/feed-digest/env` on the server, created by hand
with mode 600.

### SF Plan review

**Loose ends** (every ledger note read):

- S0 gotcha (dry run never marks posted) → **accepted, won't fix** — that is
  what a dry run is for; `RUNBOOK.md` says so.
- Plan review follow-up: nobody notices if the timer stops firing →
  **spin-off** — #41, external heartbeat check; for the final PR body.
- `Persistent=true` can post two days' entries in one digest after downtime
  → **accepted, won't fix** — D-6's cap keeps that message readable.

No loose end became a new stage.

#### Kept decisions

- D-1 — drop — the code makes it plain: `pyproject.toml` pins the one dependency
- D-2 — entry — `DECISIONS.md` › Posting
- D-3 — entry — `DECISIONS.md` › Posting
- D-4 — ADR — `docs/adr/0001-dedupe-by-stable-entry-key.md`, with its entry in `DECISIONS.md` › Feed state
- D-5 — entry — `DECISIONS.md` › Scheduling
- D-6 — drop — the cap is a named constant with its own test in `feed_digest/render.py`
- D-7 — drop — it only mattered while the plan ran; `DECISIONS.md` now exists

Approved by the maintainer on 2026-09-18.

**README, pointer line and cold reader:** `README.md` now covers install,
`feeds.toml`, the `FEED_DIGEST_WEBHOOK` variable, `pytest`, and points at
`RUNBOOK.md`. `AGENTS.md` gained the pointer line.

Cold-reader subagent (repository only, `.plan/` off limits):

| Question | First answer | Fix |
|---|---|---|
| How do I test this? | `pytest` — correct | — |
| Where is the code that decides an entry was already posted? | `feed_digest/state.py` — correct | — |
| Why is there no retry when a run fails? | "Not stated" | Added the Scheduling entry's reason; second pass answered from `DECISIONS.md` |
| Why is the webhook URL not in `feeds.toml`? | From `DECISIONS.md` › Posting — correct | — |

Second pass: four of four answered correctly.
