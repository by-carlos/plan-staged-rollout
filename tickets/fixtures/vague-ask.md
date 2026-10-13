# Fixture: vague ask

**Tracker:** GitHub, repo `example-org/reporting-app`. No template configured.

## The ask

> the reports page is slow again, can someone look at it asap

## Scripted author answers (only if the skill asks)

- What should be different when this is closed? "The monthly sales report
  should load in under 5 seconds again. It used to take about 2."
- Why now? "Finance runs month-end close next week and they use it all day."
- Which report, and since when? "The monthly sales report, since last
  Tuesday's release."
- Anything else? No answer.

## A correct run

- The floor test finds no outcome and no evidence, and asks for both in one
  message before drafting.
- The gap review hits `stands-alone`, `measurable-ac` and `title` on a draft
  built from the ask alone. After the answers, `measurable-ac` is satisfied
  by "loads in under 5 seconds".
- "asap" never reaches the title; urgency goes to priority.
- Nothing is posted.
