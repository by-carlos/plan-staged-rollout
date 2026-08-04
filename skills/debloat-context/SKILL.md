---
name: debloat-context
description: Use when per-session context overhead needs auditing or reducing — large CLAUDE.md files, long skill listings, memory indexes, or third-party advice to disable Claude Code features — and a measured, step-gated cleanup is wanted instead of blind switch-flipping.
---

# Debloat Context

Audit the fixed per-session context cost of a Claude Code setup, report ranked
findings, then apply approved trims one gated step at a time. Sized for a
cheaper model (Sonnet tier, thinking off) — every judgment call below has an
explicit rule so none is left to improvisation.

**Core principle: measure, don't assume.** Numbers from a blog post, another
machine, or a previous run are stale. Re-derive everything from this machine's
files and transcripts, this session.

## 0. Baseline

Ask the user to run `/context` and paste the output (it is a user command; the
model cannot run it). Record the total and per-category breakdown — this is the
"before" for step 4. If the user declines, proceed on file-size estimates and
say the final delta will be estimated, not measured.

## 1. Measure (read-only)

**File sizes** (≈4 chars/token):

```bash
wc -c ~/.claude/CLAUDE.md ./CLAUDE.md ~/.claude/projects/*/memory/MEMORY.md 2>/dev/null
```

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

1. Conclusion, under 40 words.
2. Bullets — one per audited item: name, applies / doesn't apply, reason under
   20 words.
3. Ranked action list — one line each with an estimated token impact, always
   labeled as an estimate. `/context` before/after is the only real
   measurement.

## 3. Act — one gated step at a time

For each action in rank order: show the exact diff or snippet → wait for an
explicit OK → apply → confirm. Never batch, never continue past a "no".

Standard actions and their guards:

1. **`skillOverrides` for unused heavy skills** — `"user-invocable-only"`
   keeps the `/name` command while hiding the description from the model.
   Verify the key format for plugin-scoped skills against current docs before
   writing it.
2. **Project CLAUDE.md trim** — on a new branch, presented as a diff, merged
   by the user's normal review flow.
3. **User CLAUDE.md trim** — copy to `CLAUDE.md.bak-<date>` first; it is
   usually not in git.
4. **Settings flags** — attempt the edit; if a permission classifier blocks
   self-editing `settings.json`, output a paste-ready snippet and move on.
   Never retry the blocked call.
5. **Memory index** — suggest `/consolidate-memory` rather than hand-pruning
   entries.

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

## Common mistakes

| Mistake | Reality |
|---|---|
| Copying deny-lists from blogs | Deferred-tool harnesses make them no-ops; measure this harness first |
| Cutting a tool or skill without checking the histogram | Zero-cost check; heavily-used items have broken workflows when cut |
| Deleting "why"/settled markers from CLAUDE.md | They prevent repeated investigations; always keep |
| Reporting estimates as measurements | Only `/context` before/after is real |
| Batch-applying all trims at once | A bad trim surfaces late; one gated step isolates it |
