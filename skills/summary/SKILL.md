---
name: summary
description: Emit a fixed, skimmable summary format — Context, numbered findings, optional Conclusion, optional Notes. Use ONLY on explicit invocation via the /summary slash command, or explicit phrases like "standard summary," "my summary format," or "give me a summary in your usual format." Do NOT use for incidental or generic requests to "summarize" something — those should get a normal, freeform answer. This skill overrides the user's default brevity rules while active.
---

# Summary format

A fixed output template, used only when explicitly requested. It exists because
some subjects (a decision with several factors, a research pass, a comparison
of options) are better read as a scannable structure than as prose — but only
when asked for by name, not as the default for every summarization request.

**Trigger discipline:** this is an opt-in format, not a general-purpose
summarizer. Invoke it for `/summary [subject]`, "standard summary," "my summary
format," or equivalent explicit requests. A bare "summarize this" or "can you
sum that up" should get a normal, freeform response — using this template
unprompted is the wrong failure mode, not a safe default.

**Brevity override:** while this format is active, it supersedes the user's
default brevity rules — the "shortest direct answer" default and any
word-count-then-offer-to-expand convention in their global CLAUDE.md. The
section budgets below (not the usual conciseness rules) govern length for this
response. Everything else — no filler openers, direct over diplomatic tone,
confidence signaling (certain / likely / guessing), flagging stale technical or
financial info, linking sources for non-obvious claims, mirroring the user's
language (English/Spanish, neutral register) — still applies inside the format.

**PII/PCI check:** before producing output, scan the subject matter for
credentials, keys, tokens, card numbers, SSNs, or other PII/PCI. If present,
flag it in one line before continuing, per standing policy.

**Subject:** if invoked with an argument (`/summary the auth refactor`),
summarize that. With no argument, summarize the current conversation or
working context.

**Too thin to summarize:** if the subject is a single fact or one-line answer,
say so in one line and answer plainly — don't pad a one-fact answer into the
full template.

## Output structure

Emit sections in this exact order. Don't label them "Section 1/2/3/4" — use
natural headers (or none) as shown below.

1. **Context** — under 50 words. **The answer itself, compressed** — what the
   solution looks like, what the verdict is, what was found. Not a recap of
   the conversation, not "this is a summary of X and why it matters." If the
   user read only this paragraph, they should already know the substance; the
   numbered list is the detail behind it. No header needed, or a light one
   like "Context."

2. **Numbered list** — the substance. This is the required core of the format.
   Items are whatever the subject calls for: facts, reasons, alternatives,
   issues, actions, risks, findings. Item count is unbounded — as many as the
   subject genuinely has, no padding to hit a round number, no truncating to
   fit one. Each item: a **bolded one-line title**, then an explanation under
   20 words, on the same line.

3. **Conclusion / recommendation** — under 50 words. Include *only* when
   there's a real conclusion, recommendation, or verdict to state. Omit this
   section entirely for purely descriptive summaries — never emit an empty or
   filler version of it.

4. **Notes** — free-form prose, up to ~250 words. Caveats, uncertainty,
   confidence levels, adjacent risks, anything worth flagging that wasn't
   directly asked for. Include only when it adds real value; omit silently
   otherwise.

Sections 1 and 2 are always required. Sections 3 and 4 are conditional — cut
them rather than leave a weak or empty version.

## Worked example

**Subject:** "give me a summary of switching this repo's CI from Travis to
GitHub Actions"

> **Context**
> Port `.travis.yml` to a GitHub Actions job matrix, re-add secrets by hand,
> rewrite the cache config, swap the README badge. Four discrete changes; the
> cache rewrite is the only non-mechanical one.
>
> 1. **Config format differs** — `.travis.yml` steps map to a YAML job matrix
>    under `.github/workflows/`, not a 1:1 port.
> 2. **Secrets need re-adding** — Travis env vars aren't copied automatically;
>    each must be re-entered as a GitHub Actions secret.
> 3. **Build cache behaves differently** — Actions caches by key+path, so the
>    old Travis cache config needs rewriting, not just moving.
> 4. **Badge URL changes** — the README status badge points at Travis; it'll
>    silently show stale state until swapped.
>
> **Recommendation**
> Migrate now — Travis is non-functional, not just slower, so there's no
> working baseline to protect. Budget for the cache rewrite; it's the part
> most likely to eat time.
>
> **Notes**
> Confidence is high on the config/secrets/badge points (mechanical, well
> documented). The cache-behavior claim is likely rather than certain — worth
> a quick check against GitHub's actions/cache docs before relying on it for a
> large build.

## Verifying it triggers

- **This repo / Claude Code:** say "give me your standard summary of X" or run
  `/summary X` and confirm the format above appears — not a plain paragraph
  answer. Also try a plain "can you summarize X" and confirm it does *not*
  trigger the template (the under-eager-not-over-eager check).
- **claude.ai:** upload the separate `summary-claude-ai.zip` variant via
  Settings → Capabilities → Skills, then ask "using your summary format,
  summarize X" in a chat and confirm the same structure appears.
