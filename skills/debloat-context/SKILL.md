---
name: debloat-context
description: Use when per-session context overhead needs auditing or reducing — large CLAUDE.md files, long skill listings, memory indexes, or third-party advice to disable Claude Code features — and a measured, step-gated cleanup is wanted instead of blind switch-flipping.
---

# Debloat Context

Audit the fixed per-session context cost of a Claude Code setup, report ranked
findings, then apply approved trims one gated step at a time. Sized for a
cheaper model (Sonnet tier, thinking off) — every judgment call below has an
explicit rule so none is left to improvisation.

**Model guidance:** the audit, report, settings, and incremental-trim steps run
fine on Sonnet. The exception is a *first deep rewrite* of a large, dense
CLAUDE.md (roughly 10 KB+ of interlocking rules): compression there risks
silent semantic drift that a diff review can miss, so run that one step on a
top-tier model (Opus class) — it is a one-off; later runs only trim increments.
If staying on Sonnet anyway, trim in small sections across multiple gated
steps, never one whole-file rewrite.

**Core principle: measure, don't assume.** Numbers from a blog post, another
machine, or a previous run are stale. Re-derive everything from this machine's
files and transcripts, this session.

## 0. Baseline

Ask the user to run `/context` and paste the output (it is a user command; the
model cannot run it). Record the total and per-category breakdown — this is the
"before" for step 4. If the user declines, proceed on file-size estimates and
say the final delta will be estimated, not measured. Either way, resolve this
**before the first edit in step 3** — a baseline captured after edits began is
worthless, and the report must state which outcome happened.

## 1. Measure (read-only)

**File sizes** (≈4 chars/token):

```bash
wc -c ~/.claude/CLAUDE.md ./CLAUDE.md ./AGENTS.md ~/.codex/AGENTS.md ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null
```

Include every harness's instruction files (`AGENTS.md`, `GEMINI.md`,
`.cursorrules`, …) — other harnesses pay the same per-session rent, and a trim
usually applies across all of them.

**Actual usage** — histogram of tool calls and skill invocations across all
transcripts. This is what separates "unused, safe to cut" from "load-bearing":

```bash
cd ~/.claude/projects
grep -rhoE '"name":"[A-Za-z_][A-Za-z0-9_]*","input"' --include=*.jsonl . | sed 's/"name":"//;s/","input"//' | sort | uniq -c | sort -rn
grep -rhoE '"skill":"[A-Za-z0-9:_-]+"' --include=*.jsonl . | sed 's/"skill":"//;s/"//' | sort | uniq -c | sort -rn
```

**Settings** — read `~/.claude/settings.json` (and the project's
`.claude/settings.json` if present); note which of `disableWorkflows`,
`disableRemoteControl`, `disableClaudeAiConnectors`, `disableArtifact`,
`disableBundledSkills`, `autoMemoryEnabled`, `skillOverrides` are already set.

**Skill inventory** — list the skills visible this session; mark the ones with
zero invocations in the histogram and long descriptions as override candidates.

**Harness check (do this before recommending anything):** if deferred tool
loading is active (a `ToolSearch` tool exists), most tool schemas are already
a bare name in a list — `permissions.deny` entries and several `disable*`
flags then save near zero. State this in the report instead of recommending
them.

## 2. Report

Fixed format, in this order:

1. `Baseline: captured | declined` — one required line.
2. Conclusion, under 40 words.
3. Bullets — one per audited item: name, applies / doesn't apply, reason under
   20 words.
4. Ranked action list — one line each with an estimated token impact, always
   labeled as an estimate. `/context` before/after is the only real
   measurement.

## 3. Act — one gated step at a time

For each action in rank order: show the exact diff or snippet → wait for an
explicit OK → apply → confirm. Never batch, never continue past a "no".

Standard actions and their guards:

1. **`skillOverrides` for unused heavy skills** — `"user-invocable-only"`
   keeps the `/name` command while hiding the description from the model.
   Known limit from live runs: **plugin-provided skills may not be affected by
   `skillOverrides` at all** — count savings only for skills the override
   demonstrably reaches, and verify the listing actually shrank after restart.
2. **Project CLAUDE.md trim** — on a new branch, presented as a diff, merged
   by the user's normal review flow.
3. **User CLAUDE.md trim** — copy to `CLAUDE.md.bak-<date>` first; it is
   usually not in git.
4. **Settings flags** — attempt the edit; if a permission classifier blocks
   self-editing `settings.json`, output a paste-ready snippet and move on.
   Never retry the blocked call.
5. **Memory** — diagnose before choosing a tool. Memory rots on a predictable
   trigger — referenced issues/PRs closing — so first extract every issue/PR
   number from the memory files and check their state in one batched call
   (`gh` REST). If claims drifted, that is **staleness, not duplication**:
   hand-correct with this procedure — read each memory before editing, check
   inbound `[[links]]` before deleting a file, update the index, then a final
   integrity pass (every index link resolves, no orphans, no dangling links).
   Reserve `/consolidate-memory` for genuine duplication; consolidating stale
   memories preserves false claims in tidier prose. Accuracy may *lengthen*
   entries — correct trade, report the real number.

**CLAUDE.md trim rules** (the part a cheap model gets wrong):

- Never delete hard rules, or "don't re-flag" / "settled in #N" / "RESOLVED"
  markers. They exist because past sessions repeated work; cutting them repays
  the saved tokens in re-investigations.
- A trim compresses rationale and moves detail into linked docs. It keeps
  every invariant, path, and cross-reference.
- Unsure whether a line is load-bearing? Keep it and flag it in the report.

## 4. Verify

The user restarts the session and runs `/context` again. Compare with the
baseline and report the delta per category. If behavior degraded, restore from
the `.bak` copy or the git branch.

When a trim moved sections into on-demand pointer files, the failure mode is
behavioral and invisible in any diff. End the report with a **watch-for
list**: the specific behaviors that would show a pointer isn't holding (e.g.
filing an issue without reading the referenced conventions doc, skipping a
pre-flight check the trimmed section used to enforce). If the user observes
one, that section comes back resident.

## Common mistakes

| Mistake | Reality |
|---|---|
| Copying deny-lists from blogs | Deferred-tool harnesses make them no-ops; measure this harness first |
| Cutting a tool or skill without checking the histogram | Zero-cost check; heavily-used items have broken workflows when cut |
| Deleting "why"/settled markers from CLAUDE.md | They prevent repeated investigations; always keep |
| Reporting estimates as measurements | Only `/context` before/after is real |
| Batch-applying all trims at once | A bad trim surfaces late; one gated step isolates it |
| Recommending `skillOverrides` for plugin skills | Plugin skills may ignore it; verify the listing shrank after restart |
| Consolidating memories that are stale, not duplicated | Merging preserves false claims in tidier prose; verify issue-state claims first |
| Treating token count as the only win | Live runs found stale/false claims worth more than the tokens saved |
