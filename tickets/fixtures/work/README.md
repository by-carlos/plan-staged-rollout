# work-issue fixtures

Fetched tickets, in the shape an adapter's `fetch` returns, for exercising
`work-issue` and `scripts/work_core.py` without a tracker. Every repo, key,
site and person is a placeholder.

| File | What it exercises |
|---|---|
| `github-act.json` | A GitHub issue with an AI prompt (a block quote ending on how to verify) and board fields. `assess` returns `act`; the base is the repo's default branch. |
| `github-guide.json` | The same issue with no AI prompt. `assess` returns `guide`: an interpretation and a step plan, no branch and no writes. |
| `jira-act.json` | A Jira ticket whose AI prompt names the repository and base branch on labelled lines. `assess` returns `act` with both read from the prompt. |
| `jira-ask.json` | A Jira ticket whose AI prompt names neither. `assess` returns `ask` with `needs_user` listing both; the skill asks before branching. |
| `status-routed.toml` | A GitHub template with a routed board, a Status field, `[work].status` and a stricter merge command, for `status` and `merge-command`. |
