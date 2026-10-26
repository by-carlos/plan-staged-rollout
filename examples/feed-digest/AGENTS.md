# AGENTS.md — feed-digest

- Run `pytest` before pushing; `feed-digest run --dry-run` never posts.
- The webhook URL is a secret: it lives only in `FEED_DIGEST_WEBHOOK`.
- **Decisions in force live in [`DECISIONS.md`](DECISIONS.md).** Read the area covering a path before changing it, and add or edit an entry in the same pull request when a change settles something future work must respect.
