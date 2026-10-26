<!-- decisions-format: 1 -->
# Decisions

Decisions in force. Read the area that covers a path before changing it; add
or edit an entry in the same pull request when a change settles something
future work must respect.

ADRs: docs/adr/

## Posting

Paths: `feed_digest/post.py`, `feed_digest/render.py`, `feeds.toml`

- **The digest goes to one chat channel through an incoming webhook — not
  email, not a bot account.** — the team already reads the channel, and a
  one-way post needs no credentials to manage. Revisit: if replies or
  per-person digests are wanted. Source: #3
- **The webhook URL is read only from `FEED_DIGEST_WEBHOOK`; it never goes in
  `feeds.toml`, a test or a log line.** — `feeds.toml` is committed, and the
  URL alone is enough to post as the job. Revisit: never. Source: #3

## Feed state

Paths: `feed_digest/state.py`, `feed_digest/fetch.py`, `feed_digest/cli.py`

- **An entry is recorded as posted only after the webhook answers 2xx, keyed
  by the feed's `id` or else a hash of link and title, in the SQLite state
  file.** — this is what makes a rerun safe and nothing post twice. Revisit:
  never. Source: ADR 0001

## Scheduling

Paths: `deploy/`, `RUNBOOK.md`

- **One run a day from a systemd timer, with no retry loop; a missed run is
  picked up by the next one.** — reruns are safe (Feed state), so the next
  day's run already is the retry. Revisit: if a missed day turns out to
  matter to the team. Source: #5
