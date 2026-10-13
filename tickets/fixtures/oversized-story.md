# Fixture: oversized story

**Tracker:** Jira, site `example.atlassian.net`, project `DEMO`. Template:
`guarded-example.toml` (story-point matrix).

## The ask

> Create a story for the new partner onboarding. Partners need a sign-up
> form, email verification, an approval queue for our admins, an audit log
> of every approval, a CSV export of approved partners, and we need to
> migrate the 40,000 partners from the old spreadsheet into the new tables.
> The work lands in `example-org/partner-portal` on `main`. Done when a new
> partner can sign up and be approved end to end, and every migrated partner
> can log in.

## Scripted author answers (only if the skill asks)

- Existing process? "No, nothing like this exists yet."
- Roughly how many days? "More than a week, probably several."
- How many unknowns? "Many: we have never done the email verification."
- Depends on another team? "Yes, the identity team owns email sending."

## A correct run

- The estimate lands on a `split` cell, so no number is proposed; the skill
  proposes a split into smaller stories instead.
- The gap review hits `size` (and likely `dependencies` until the identity
  team is named).
- The guarded sensitive-data field is not touched by the ask, so it stays unset without a
  question.
- Nothing is posted.
