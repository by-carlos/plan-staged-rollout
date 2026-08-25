# The end-to-end proof of concept

Everything a full **"on the run"** lifecycle run consumes, ready to drop into a
throwaway repository: a four-stage plan, and the verification script that
decides whether the run worked ([#110](https://github.com/by-carlos/plan-staged-rollout/issues/110)).

The run itself is a **manual act by the maintainer** — driven from a phone,
start to finish, with the computer off. Nothing in this directory can perform
it. These are the inputs; the run produces the evidence.

**This has now been run once, and it passed** (#110). What follows is still
written as inputs, because that is what they are for the next run — but the
fixes in them came from the first one, not from review.

> **Deliberately not run against this repository.** Using this plugin's own
> mechanism to build its cloud mode would be circular and would muddle the
> record, so the proof of concept uses a disposable repository.

## What the plan is shaped to prove

| Stage | Gate | What it establishes |
|---|---|---|
| S0 Slug core | `auto` | A fired routine makes real edits and opens a real PR, unattended |
| S1 CLI | `auto` | A second fired stage builds on the first through the plan branch alone |
| S2 License choice | `human` | The orchestrator refuses to fire it, the maintainer runs it interactively, the orchestrator resumes |
| SF Closeout | `auto` | Pass/fail is produced by a command, and the plan-to-main merge is left for a person |

Two things stay manual by design, and the run is only a proof if both are
exercised: the `gate: human` stage, and the final `plan-slugify` → `main`
merge. Note the split on that last one — SF **opens** the plan-to-main pull
request as its final act and the maintainer **merges** it. Only the merge is
manual; a closeout that cannot open the PR just leaves clerical work behind.

S2 must exercise the **whole** path — refusal, interactive run, resume. A run
that only proves the refusal has proved half of it.

Every stage runs at the model and effort in the stage index, which are real
values, not placeholders. The point is to measure what a run actually costs
and ships.

## Setting up the throwaway repository

1. Create an empty repository with a `main` branch and one commit.
2. Copy `.plan/` to the repository root and `verify_run.py` to
   `scripts/verify_run.py`.
3. Commit both on a `plan-slugify` branch cut from `main`, and push it with an
   upstream. `.plan/` **tracked on the plan branch** and the plan branch
   **having an upstream** are load-bearing, not housekeeping.
4. Create one stage-runner routine per model the stage index names (`opus` and
   `sonnet`), each carrying
   [`../stage-runner-prompt.md`](../stage-runner-prompt.md), the repository,
   and its model in `job_config.ccr.session_context.model`. A run cannot change
   its own model.
5. Start an interactive session carrying
   [`../orchestrator-prompt.md`](../orchestrator-prompt.md).

From there the phone drives it: the orchestrator reads the plan branch, fires
one stage, waits for the ledger to settle, repeats — stopping at S2 and again
before the final merge.

## The verification script

`verify_run.py` is the run's pass/fail. SF runs it; its exit status is the
result, and its output is the evidence pasted into the ledger.

```
python3 scripts/verify_run.py --repo .
```

It asserts, reading everything through `git show <ref>:<path>` and preferring
`origin/<branch>` so it judges what was actually **pushed**:

1. every stage branch's work reached the plan branch — the branch itself may
   be gone, since the stage-runner contract deletes it after its PR merges, and
   absence fails only when no merged PR accounts for it;
2. every stage's pull request is closed as merged, and targeted the plan
   branch;
3. `.plan/LEDGER.md` has every row settled — nothing at `doing`, `todo` or
   `blocked`, and no manifest stage missing a row;
4. the edits each stage claimed are present on the plan branch;
5. nothing reached the default branch — not the plan branch, not a stage
   branch, not a stage's files.

Stdlib only, Python 3.11+, and no network call of its own.

**Squash merges make ancestry meaningless**, so check 1 is layered: if the
stage tip is an ancestor of the plan branch, that settles it; otherwise the
script diffs the branch against its merge base and asserts every path it
touched is present on the plan branch, with the PR's merged state as the
authoritative signal. This is why check 2 is not redundant with check 1.

### The two data files

- **`.plan/verify-manifest.json`** — the branches, and per stage the
  `expect_paths` and `expect_contains` pairs that make "the stage did what it
  claimed" a checkable assertion rather than a judgement. Committed here,
  ready to use.
- **`.plan/pr-states.json`** — written by SF from the GitHub MCP server
  (`mcp__github__pull_request_read`). **There is no `gh` in a routine run**,
  and the script deliberately makes no API call of its own, so PR state has to
  be captured into the repository by the stage that can reach GitHub. One
  object per stage id:

  ```json
  {"S0": {"number": 1, "state": "closed", "merged": true, "base": "plan-slugify"}}
  ```

  SF must read each state back from GitHub rather than writing what it
  believes to be true.

Both are looked up in the working tree first, then on the plan branch;
`--manifest` and `--pr-states` override.

## Reading the result

A pass is `VERIFICATION PASSED` with exit `0`, *plus* confirmation that the
whole run — every stage fire, the human-input step, and the final manual merge
— was driven from a phone with the computer off throughout. The script cannot
check that second half; only the maintainer can attest to it.

**The passing run is the one taken before the final merge, and it does not
reproduce afterwards.** Check 5 asserts that nothing has reached the default
branch, so once the maintainer merges the plan-to-main pull request — the last
step of a *successful* run — re-running the script fails that check. This is
the check working, not the run breaking. The result of record is the output SF
pasted into its ledger notes at closeout; a later re-run is measuring a
different repository state and answers a different question.

If verification fails, SF marks its own row `blocked` and writes
`.plan/BLOCKED.md`. A closeout that repairs its own subject proves nothing.

## Where findings go

Findings about the stage-runner or orchestrator contracts are **recorded and
routed to the owning issue**, never folded straight into
[`../stage-runner-prompt.md`](../stage-runner-prompt.md) or
[`../orchestrator-prompt.md`](../orchestrator-prompt.md) from inside the run —
each contract has its own issue, and an in-place edit made mid-run loses which
evidence prompted it.

And this exercise does not decide whether "on the run" becomes a documented,
supported plugin mode. It proves the lifecycle once; the packaging decision is
separate, and uses this run's findings as evidence.
