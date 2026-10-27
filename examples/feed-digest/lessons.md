## Lessons

### Lessons from this plan

🧭 **For you, next time**
- The plan review's first change (new D-3) was that D-2's webhook sat in committed `feeds.toml`, against ranked constraint 2 (the URL never reaches the repository) — check each frozen decision against the ranked constraints when drafting, before the review.
- S2 was `gate: local` and ran on the laptop because the server is unreachable from a cloud session; `/etc/feed-digest/env` was created by hand and never committed — name host-only setup like this in the stage's Steps at bootstrap, so no unattended run reaches it by surprise.
- Failure visibility stopped at the journal (constraint 4), and the review had to spin off #41 for a timer that stops firing — put "how do we know it stopped" in Done as a check, not as a follow-up.
- D-5's no-retry reasoning survived into `DECISIONS.md` only after the cold reader's first pass answered "Not stated" — when promoting a decision, copy its reason and its rejected alternative, not just the choice.

🔧 **For the plugin**
- SF's cold-reader pass found a promoted entry (Scheduling) missing its reason, and a fix was needed on the second pass — the kept-decisions step should draft each entry with the frozen decision's reason and rejected options included.
