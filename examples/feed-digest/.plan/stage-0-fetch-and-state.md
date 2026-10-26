# S0 — Fetch and state (keystone)

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.

## Goal

Fetch every feed in `feeds.toml` and return only the entries not yet posted,
with the state file that remembers them. S1 renders and posts what this
returns; S2 schedules the command that calls it.

## Steps

- [x] Add `feeds.toml` (name + URL per feed) and its loader; pin `feedparser`
  in `pyproject.toml` (D-1).
- [x] `fetch.py`: download each feed with a 20-second timeout and a 5 MB cap;
  a feed that fails is logged by name and skipped, never fatal to the run.
- [x] `state.py`: SQLite state file with the entry key of D-4; `new_entries()`
  returns unseen entries, `mark_posted()` records them in one transaction.
- [x] `cli.py`: `feed-digest run --dry-run` prints the new entries' titles.
- [x] Fixture feeds under `tests/fixtures/` (one without `id`s) and tests.

## Acceptance

- `pytest` passes.
- `feed-digest run --dry-run --feeds tests/fixtures/feeds.toml` lists the
  fixture entries; after `mark_posted`, a second run lists none.
- A fixture feed that times out is reported by name and the others still run.

## Artifacts

`feeds.toml`, `pyproject.toml` (new dependency: `feedparser`),
`feed_digest/fetch.py`, `feed_digest/state.py`, `feed_digest/cli.py`,
`tests/`. The state file (`state.db`) is runtime data and is git-ignored.
