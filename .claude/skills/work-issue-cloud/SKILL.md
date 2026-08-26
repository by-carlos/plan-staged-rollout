---
name: work-issue-cloud
description: Unattended cloud-executor variant of work-issue — a claude --cloud session works one GitHub issue end-to-end inside a batch run, branch claude/issue-<n> off the run branch, PR into the run branch, self-merge, status label handoff. Use ONLY when fired by the work-issues orchestrator inside a cloud session with an issue number and a run branch named in the prompt. Never invoke in an interactive local session — the local work-issue skill owns that path.
---

The cloud half of the `work-issues` batch workflow: one unattended
`claude --cloud` session, one issue, one merged change on the run branch —
or a clean, resumable stop. This file is committed to the target repo's own
`.claude/skills/` because a cloud session does not load plugins today
(server-side feature gate, off as of Aug 2026 — see by-carlos/claude-lab#35);
revisit plugin delivery if that gate flips on.

The orchestrator's fire prompt supplies two inputs: the **issue number** and
the **run branch** (`run/<UTC-timestamp>`, cut from `main`). The session is
cloned at the run branch. If either input is missing from the prompt, stop
immediately and post nothing — a guessed run branch is how work lands in the
wrong place.

## Ground rules — the never-do list

- **Never touch `main`**, or any branch other than this issue's own
  `claude/issue-<n>` branch and the run branch. The run branch itself is only
  ever changed by merging this issue's PR into it.
- **Never force-push**, to anything.
- **Zero writes to the Projects v2 board.** Not reachable from a cloud session
  anyway (no `gh` binary; the GitHub MCP surface has no Projects tools) — the
  orchestrator owns every board write, and the `status:*` labels below are the
  only channel back to it.
- **Never close the issue.** Per-issue PRs merge into the run branch, so
  `Closes #n` fires nothing; the final run→`main` PR carries the whole
  `Closes` list, and closing by hand here would skip review of the batch.
- **No user interaction, ever.** Nobody is watching. Every gate the local
  `work-issue` skill asks a person about becomes stop-and-label here: where
  that skill would raise a question, this one stops, comments why, and applies
  `status:stuck` or `status:needs-local`.
- **No secrets in output.** Anything that looks like a credential in code,
  logs, or config: stop and label `status:needs-local` — flagging to a person
  is a local session's job.

## GitHub access — MCP only, scoped, deferred

- **There is no `gh` and no direct API.** Every GitHub read/write goes through
  the `github` MCP server's tools. Their schemas are deferred: before the
  first GitHub call, load them with one `ToolSearch` call covering every tool
  the run needs (issue read/write, comments, labels, PR create/merge) — budget
  that round trip once, up front, not per call.
- **The session is hard-scoped to the repo(s) in its `sources`.** Calls
  against any other repo are refused server-side. Qualify every call with the
  target repo, and never use repo-less search or list tools — the session's
  own scope block warns they can reach past the allowlist.
- **Label writes are set-semantics.** The one tool that touches labels
  (`issue_write`, `method: update`) replaces the issue's entire `labels`
  array. To set a status label: read the issue's current labels, drop any
  existing `status:*` entry, add the new one, and write the **full merged
  set** back. A naive "add this label" write silently strips every other
  label on the issue.

## Procedure

1. **Read the full issue thread** — body and comments; decisions live in the
   comments. Read the target repo's own `CLAUDE.md` and conventions before
   planning the change. If the issue is plainly not workable unattended
   (needs a person's account, a GUI, a design decision the thread doesn't
   settle, or scope far beyond one session), stop here: comment why, label
   `status:needs-local` (capability gap) or `status:stuck` (everything else),
   and end. That is a successful run of this contract, not a failure.
2. **Announce.** Post one comment on the issue before the first commit:
   `🤖 Claude Code cloud session <session-id> picking this up — <one line on
   the approach>. Run branch: <run branch>. Branch: <branch>.`
   Include the session id when the environment exposes one; measured cloud
   sessions (26 Aug 2026) had none to read, and the comment is valid without
   it. One announcement per session. The comment is part of the handoff unit —
   it is how a later local session finds this one.
3. **Branch** `claude/issue-<n>` off the run branch. The cloud platform may
   append its own uniquifying suffix to a branch it creates (measured:
   `claude/issue-48-2ol742`); that is fine — the announcement comment and the
   PR, not the naming pattern, are authoritative for the actual branch name,
   so state the real name in both.
4. **Implement** following the target repo's conventions, committing each
   logical unit with conventional commit messages. If the repo keeps a
   changelog whose rules cover this change, add the entry as part of the work
   — the per-issue PR skips the changelog CI gate (it is scoped to
   `base: main`), but the entry must exist for the final run→`main` PR to
   carry.
5. **Push the branch and open a PR** from `claude/issue-<n>` into the run
   branch. Body: what changed and why, trade-offs worth a reviewer's
   attention, and a plain reference to the issue (`#<n>` — not `Closes`,
   which belongs to the final PR). Every claim in the body is something that
   actually ran in this session, or is written as unverified.
6. **Resolve conflicts yourself, locally.** If the PR reports conflicts —
   `CHANGELOG.md` against a parallel issue's work is the expected case —
   merge the run branch into `claude/issue-<n>` locally, keep **both**
   changelog entries, commit the merge, and push. Never resolve through
   GitHub's web editor, never rely on a server-side merge driver, never
   force-push.
7. **Squash-merge the PR yourself** into the run branch. No gate — the run
   branch is unprotected by design, and review happens once, at run→`main`.
   The repo deletes the merged branch automatically
   (`delete_branch_on_merge`).
8. **Label and report.** Set `status:done-in-run` (set-semantics, per above)
   and post a result comment: what merged, the PR link, and anything the
   final reviewer should look at. Leave the issue open.

## Failure protocol — stop, label, leave a resumable trail

On any failure the session cannot resolve itself, in this order:

1. **Push whatever committed work exists** on `claude/issue-<n>` (never
   force). If commits exist and no PR is open yet, open the PR into the run
   branch anyway and leave it open, unmerged — the **handoff unit is the
   pushed branch + the open PR + this session's comments**, the only
   artifacts that survive the VM. Uncommitted scraps not worth a commit die
   with the VM; say so in the comment.
2. **Comment on the issue**: what was attempted, exactly where it stopped,
   why, and what a resuming session should do first.
3. **Label** (set-semantics): `status:needs-local` when finishing requires
   something a cloud session cannot do — board writes, credentials, a GUI, a
   person's judgment, access outside the session's repo scope.
   `status:stuck` for everything else. Exactly one `status:*` label at a
   time.
4. **Stop.** No retry loops past a second attempt at the same step, no
   speculative fixes, and `main` and the run branch left exactly as found.

A later local session picks the issue up with
`/work-issue <n> --resume` against the branch and PR this leaves behind.

## Failure cases

| Situation | What to do |
|---|---|
| Fire prompt names no issue or no run branch | Stop silently — post nothing anywhere. |
| Run branch doesn't exist in the clone | Stop; comment on the issue; `status:stuck`. Never cut one from `main` yourself. |
| A GitHub MCP call is refused as out of repo scope | The work needs a repo the orchestrator didn't grant: comment naming it; `status:stuck`. |
| Issue needs board writes, credentials, a GUI, or a person's call | Comment why; `status:needs-local`. |
| Changelog (or any) conflict against a parallel issue | Merge the run branch in locally, keep both entries, push (step 6). Only if the conflict is semantic — two issues editing the same behaviour — stop and `status:stuck`. |
| PR merge is refused by branch protection | The run branch is misprovisioned; comment; `status:stuck`. Never merge by another route. |
| Tests or CI on the per-issue PR fail and the fix isn't evident | Comment with the failing output; `status:stuck`. Never merge red. |
| Label write fails | Retry once; if still failing, say so in the result comment — the comment is the fallback channel. |
| The issue is already labelled `status:done-in-run` | A previous run finished it: comment that this run found it done and stop. Merge nothing twice. |
