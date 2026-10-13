# GitHub adapter fixtures

Recorded-shape responses and placeholder inputs for `tests/test_github_adapter.py`.
Nothing here is real: the owner, repo, board numbers and ids are placeholders.

| File | What it is |
|---|---|
| `routed.toml` | A template with routing, board field mapping, a closed label list and one extra select field. |
| `draft-routed.json` | A draft for `example-org/widgets`, with a non-ASCII body, ready for `build`. |
| `issue-view.json` | The shape `gh issue view --json ...` returns, with CRLF bodies as GitHub stores them. |
| `graphql-board.json` | The board-field read-back query's response, with items on two boards. |
| `project-field-list.json` | `gh project field-list --format json`. |
| `issue-types.json` | `orgs/{owner}/issue-types`. |
