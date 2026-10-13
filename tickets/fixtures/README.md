# Fixtures

Synthetic inputs for exercising `create-issue` by hand in dry-run mode, and
for adapter tests. Nothing here is real: every name, repo, project and field
id is a placeholder.

| File | What it exercises |
|---|---|
| `vague-ask.md` | A one-line ask. Expect the floor test to ask first, and the review to hit `stands-alone`, `measurable-ac` and `title`. |
| `oversized-story.md` | A story far bigger than one iteration. Expect the estimate to come out as `split` and the review to hit `size`. |
| `regulated-data.md` | An ask that may touch payment-card data, run on `guarded-example.toml`. Expect the review to hit `guarded-field` and ask; the field must stay unset. |
| `guarded-example.toml` | A Jira template that extends the default and declares one guarded field and a story-point matrix, on placeholder ids. |
| `malformed-template.toml` | A template with several deliberate errors; the loader must reject it and list them all. |

Each `*.md` fixture holds the ask as a user would type it, the scripted
answers the "author" gives if the skill asks, and what a correct run does.
The `*.draft.json` files are the drafts a dry run produced, kept so adapter
stages can test `build` against them.
