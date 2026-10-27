# S1 — Render and post

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.

## Goal

Turn S0's new entries into one digest message and post it to the webhook, so
a real run delivers to the team channel. S2 schedules it.

## Steps

- [x] `render.py`: group entries by feed, one line each (title + link), cap
  at the D-6 limit with a "+N more" line. Revisit D-6 against the fixtures.
- [x] `post.py`: read the URL from `FEED_DIGEST_WEBHOOK` only (D-3); exit
  with a clear message, without printing the value, when it is unset.
- [x] `cli.py`: `run` posts, then calls `mark_posted()` only after a 2xx
  response (D-4); `--dry-run` prints the digest instead of posting.
- [x] Tests: digest shape, the cap, and a failed post leaving state untouched.

## Acceptance

- `pytest` passes.
- `feed-digest run --dry-run --feeds tests/fixtures/feeds.toml` prints one
  digest; a second run prints "no new entries".
- `FEED_DIGEST_WEBHOOK` unset → exit code 2 and a message naming the
  variable, not its value.

## Artifacts

`feed_digest/render.py`, `feed_digest/post.py`, `feed_digest/cli.py`,
`tests/`. Secret: the webhook URL lives only in the environment — never in
`feeds.toml`, a test, or a log line.
