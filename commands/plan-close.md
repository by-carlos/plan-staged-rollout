---
description: Close out a finished staged-rollout .plan/ — verify completion, distill the story into a final PR body, clean up .plan/, and propose the PR to main.
---

# /plan-close — closeout

Finish a `.plan/` that has run its course: verify every stage is settled,
preserve the story, clean up, and propose the final PR. This command is a
**thin wrapper**: the source of truth for what happened is the project's own
`.plan/PLAN.md` and `.plan/LEDGER.md`. Do not re-derive the story from the
repo or git log — distill it from those two files.

Work through these steps **in order**:

1. **Locate `.plan/`.** Find the `.plan/` directory at the repo root. If it
   is absent from the working tree, do **not** conclude there is no plan —
   you may simply be on `main` while the plan lives on its branch. Run
   `git fetch origin`, then look for `plan-*` branches: local first, then
   remote. If a plan branch exists, offer to check it out (that makes
   `.plan/` appear) and continue from there. Closeout runs **in the main
   clone**, on the plan branch — never inside a stage worktree.
   Only when no plan branch exists
   anywhere, stop and tell the user there is nothing to close (or that they
   may want to bootstrap one — "bootstrap a plan for \<idea>", or the
   explicit command `/plan-staged-rollout:plan-stages <idea>` — if they meant
   to start one).

2. **Preflight, then completion gate.** First run `PLAN.md`'s **Preflight &
   sync** block (Operating protocol, step 0) — the ledger may only be read
   after the plan branch is synced, and the preflight's reconcile step is
   part of this gate: a `done` row whose stage PR is still open or unmerged
   is a gate failure (the work isn't on the plan branch), not a pass. Then
   read `.plan/LEDGER.md`'s status table. Every row must be `done` or
   `skipped` — this includes any stages the final review stage (`SF`)
   spawned — **and** `gh pr list --base plan-<slug> --state open` must show
   no remaining stage PRs. If any row is `todo`, `doing`, or `blocked`,
   **refuse to run**: list exactly which stages are pending, their status,
   and what to run instead — "run stage \<N> of the plan", or the explicit
   command `/plan-staged-rollout:plan-run <N>`, for `todo`/`doing`, or
   resolve the `blocked` runbook first. Stop there — do not proceed to
   distillation or cleanup.

   **Stage worktrees are part of this gate.** `git worktree list` must show
   only the clone plus worktrees whose branch matches `plan-<slug>-s*` — an
   operator's unrelated worktree (any other branch) is none of this plan's
   business and does not block closeout. A surviving worktree on a matching
   branch means some stage never finished its teardown (finish step 5) —
   report each path and what it holds, and refuse to close until they are
   resolved. Removing one is the operator's call, never automatic, and never
   with `--force`.

3. **Distill the story — dispatch a subagent.** `.plan/PLAN.md` and the full
   `.plan/LEDGER.md` are the largest material this command touches, and
   nothing after this step needs them once the PR body exists — so don't keep
   them resident. Dispatch a `sonnet` subagent (not a cheaper tier: turning
   the ledger's raw notes into a readable summary rather than a paste is a
   judgment call on register, the same call the issue-body contract makes for
   its plain-language section — a cheaper tier tends to paste, and the failure
   is only visible to someone who reads the source material it was built from,
   which is exactly the reader who no longer exists after closeout) carrying:
   - the paths to `.plan/PLAN.md` and `.plan/LEDGER.md`;
   - the required body shape — what was built and why (from `PLAN.md`'s
     opening + frozen decisions), the stage-by-stage as-built summary (from
     the ledger notes), and any spin-off candidates and accepted-won't-fix
     items the `SF` review stage recorded, called out explicitly as follow-up
     work;
   - the instruction not to just paste the raw files, but to summarize them
     into a readable PR description.

   The subagent returns **PR body text only** — it must not write files, run
   git, or call `gh`. Every write stays here in the parent: the `.plan/`
   cleanup commit (step 4), the branch push and the final PR proposal
   (step 5). Only dispatch after step 2's gate has passed — a gate failure is
   a decision that cannot leave this session.

4. **Clean up `.plan/`.** Offer the user a choice: delete `.plan/` as the last
   commit on the plan branch (the default — nothing is lost, the full plan
   history remains in git), or keep it in place for projects where the plan
   doubles as documentation. Act on their choice; if deleting, make it its own
   commit (conventional message, e.g. `chore(plan): remove .plan/ at
   closeout`) and wait for the user's OK before committing, same as any other
   change.

5. **Propose the final PR.** Push the plan branch, then propose the PR from it
   to `main` using the distilled body from step 3. Unlike the per-stage PRs
   (which are squash-merged), this final PR is a **normal (non-squash) merge**,
   so each stage's squashed commit lands on `main` as its own distinct commit
   and the as-built history survives. Wait for the user to review and merge —
   never merge into `main` unilaterally. The plan's `merge` flag does not
   apply here: it governs stage PRs only, and closeout never reads it.

6. **End announcement.** State explicitly: the plan is **closed**, the final
   PR has been proposed (or opened, if the user acted on it during this
   session), and there is nothing left to run. Then stop.
