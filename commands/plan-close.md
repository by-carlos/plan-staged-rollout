---
description: Close out a finished staged-rollout .plan/ — verify completion, distill the story into a final PR body, clean up .plan/, and propose the PR to main.
argument-hint: [--unattended]
---

# /plan-close — closeout

Finish a `.plan/` that has run its course: verify every stage is settled,
preserve the story, clean up, and propose the final PR. This command is a
**thin wrapper**: the source of truth for what happened is the project's own
`.plan/PLAN.md` and `.plan/LEDGER.md`. Do not re-derive the story from the
repo or git log — distill it from those two files.

If `$ARGUMENTS` carries the token **`--unattended`**, this session has nobody
to answer it — it was launched by an unattended runner (`plan_driver.py` runs
closeout itself once every stage is settled), or the user is walking away.
The token selects **declared default over ask**, never "proceed anyway": every
question below either has an answer already written on `PLAN.md`'s plan flags
line or is a hard stop, per the `staged-rollout` skill's *Unattended mode*.
Honour it in steps 1, 2, 4 and 5. Without the token nothing changes — every
gate and offer below works exactly as it always has. **In neither mode does
this command merge the plan→main PR**; that gate survives every mode and has
no flag.

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

   **Unattended:** the checkout is the declared default when there is exactly
   one candidate — a single `plan-*` branch, local or remote — so check it out
   and carry on without asking. Two or more matching branches is a hard stop:
   there is no way to guess which plan was meant, so name them all and end.

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
   distillation or cleanup. This gate is a **hard stop in both modes** —
   unattended, it has no default to fall back on, so report the same way and
   end.

   **Stage worktrees are part of this gate — one rule, two modes.**
   `git worktree list` must show only the clone plus worktrees whose branch
   matches `plan-<slug>-s*`; an operator's unrelated worktree (any other
   branch) is none of this plan's business and does not block closeout. A
   surviving worktree on a matching branch means some stage never finished
   its teardown (`PLAN.md` finish step 5), so classify each one:

   - **Finished work — safe to remove.** Its stage branch is merged into the
     plan branch and it holds nothing unpushed: no unpushed commits, no
     stash, and no modification to a tracked file. `--unattended` removes it
     (`git worktree remove <path>`, then `git branch -D plan-<slug>-s<N>` —
     `-D` because the squash merge means git never sees the branch as
     merged); interactively, **offer** the same removal and act on the
     answer. Either way, say which paths were removed.
   - **Anything else — hard stop, in both modes.** Unpushed commits, an
     unmerged branch, a stash, or a modified tracked file means the worktree
     may hold work git cannot recover. Report each path and exactly what is
     in it, say what would clear it, and refuse to close. Never `--force`,
     and never `git worktree prune` to tidy up.

   Untracked files alone do not decide this either way: they are reported as
   part of "what it holds", so a genuine leftover surfaces rather than
   vanishing, but they do not by themselves make a merged, fully-pushed
   worktree unsafe.

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

4. **Clean up `.plan/`.** Read the **`plan-dir`** entry on `PLAN.md`'s plan
   flags line, under the stage index — `delete` or `keep`, and an absent
   entry (or an absent flags line) reads as `delete`. That value is the
   plan's declared answer: delete `.plan/` as the last commit on the plan
   branch (nothing is lost — the full plan history remains in git and the
   final PR shows the removal), or keep it in place for a project where the
   plan doubles as documentation. Offer the user the choice with that value
   as the recommendation, and act on their answer; if deleting, make it its
   own commit (conventional message, e.g. `chore(plan): remove .plan/ at
   closeout`) and wait for the user's OK before committing, same as any other
   change.

   **Unattended:** apply the flag without asking, and commit without waiting
   for an OK — declaring the flag *is* the OK, exactly as `merge: auto` is
   for a stage PR.

5. **Propose the final PR.** Push the plan branch, then propose the PR from it
   to `main` using the distilled body from step 3. Unlike the per-stage PRs
   (which are squash-merged), this final PR is a **normal (non-squash) merge**,
   so each stage's squashed commit lands on `main` as its own distinct commit
   and the as-built history survives. Wait for the user to review and merge —
   never merge into `main` unilaterally. The plan's `merge` flag does not
   apply here: it governs stage PRs only, and closeout never reads it.

   **Unattended:** open the PR rather than offering to — an open PR is what
   the operator is coming back to, and opening it changes nothing on `main`.
   Pin the base explicitly (`gh pr create --base main`, or the repo's actual
   default branch) rather than relying on `gh`'s default. Then **stop**:
   merging it is the human gate that survives every mode, and no flag,
   argument or runner may take it. Print the PR URL in the end announcement
   so an unattended runner's notification carries it.

6. **End announcement.** State explicitly: the plan is **closed**, the final
   PR has been proposed (or opened, if the user acted on it during this
   session, or always under `--unattended`) with its URL, which worktrees
   were removed and which `.plan/` decision was applied, and that there is
   nothing left to run **except the merge, which is the user's**. Then stop.
