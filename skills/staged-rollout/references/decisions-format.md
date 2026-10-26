<!-- decisions-format: 1 -->
# `DECISIONS.md` — format

A repository's `DECISIONS.md` lists the decisions **still in force**, one short
entry each, grouped by area, so the next piece of work does not quietly undo
them. This document is the whole format: it is self-contained, and every tool
that reads or writes the file carries an identical copy of it.

## Version

The first line of this document, and of every `DECISIONS.md` written to it, is
the format-version line:

```
<!-- decisions-format: 1 -->
```

The number changes only when the shape below changes in a way an older reader
would misread. Two copies of this document with the same version must be
identical; a copy that differs is a defect in that copy.

## What gets kept

A decision is kept when **any one** of these holds:

- someone could plausibly undo or redo it without knowing it was decided;
- it took a spike, a review or real alternatives to settle;
- the code does not make it obvious.

Otherwise git is enough: the commit and its pull request already say it.

When a body of work ends, each decision it made gets one of three outcomes,
and the person who owns the repository approves the whole list at once:

- **Drop it** — it only mattered while the work ran, or the code already makes
  it plain.
- **An entry in `DECISIONS.md`** — the default for anything kept.
- **An ADR** — only for a big decision that is hard to reverse, had real
  alternatives, and whose reasoning has no other home once the working notes
  are gone. An ADR decision also gets an entry, which links to the ADR.

## Where it lives

Adopt what the repository already has; never start a parallel list.

- **An existing ADR folder** — `docs/adr/`, `doc/adr/`, `adr/`, or
  `docs/decisions/` holding numbered files — receives new ADRs in its own
  format and numbering.
- **An existing current-decisions document** is the target: new entries go
  there, in its format.
- **Otherwise** create `DECISIONS.md` at the repository root, to this format.
  If an ADR folder exists, the file names it on the line under its title:
  `ADRs: docs/adr/`.

When more than one candidate exists, or it is unclear whether a document is a
current-decisions list, ask before writing.

## Shape

```markdown
<!-- decisions-format: 1 -->
# Decisions

Decisions in force. Read the area that covers a path before changing it; add
or edit an entry in the same pull request when a change settles something
future work must respect.

ADRs: docs/adr/

## API

Paths: `src/api/`, `openapi.yaml`

- **Every endpoint is versioned in the path (`/v1/…`), never by header.** —
  clients cache by URL. Revisit: if a gateway takes over versioning.
  Source: #142
- **Pagination is cursor-based; offset paging is not offered.** — offset
  scans timed out past 1M rows. Revisit: never. Source: ADR 0004

## Infrastructure

Paths: `infra/`, `.github/workflows/deploy.yml`

- **One resource group per environment, named `rg-<app>-<env>`.** — access
  is granted per group. Revisit: if environments share a subscription.
  Source: #87
```

- **Areas** are `##` headings, named for a part of the system a reader would
  recognise. Each area's first line is `Paths:` with the repository-relative
  paths it covers, in backticks, comma-separated. A path ending in `/` covers
  everything below it; `*` and `**` are globs; `.` alone covers the whole
  repository. Tools pick the entries for a change by matching its files
  against these paths, so a path list that is too broad shows the entries
  everywhere and one that is too narrow hides them.
- **Entries** are bullets, one to three lines:
  `**<the rule now in force>** — <why, in one clause>. Revisit: <the
  condition that would reopen it, or "never">. Source: <issue, pull request
  or ADR>.` State the decision as the rule, not as its history ("we moved
  from X to Y" is history; "Y, not X" is the rule).
- **Order** areas by how often they are touched, entries within an area by
  importance. No numbering — an entry is found by its area and its words, and
  numbers would have to be kept stable through deletions.

## Current only

`DECISIONS.md` holds current decisions only. A decision that is replaced is
**edited in place or deleted** — never marked superseded, struck through, or
moved to a history section. Git keeps the history.

## Splitting

Past roughly 40 entries, an area that sits in one folder moves to its own
`DECISIONS.md` in that folder, in this same format, with the same
repository-relative paths. The root file keeps the area heading with a single
line in place of its entries: `Moved: <folder>/DECISIONS.md`. A reader looking
for the entries that cover a path checks the root file and every
`DECISIONS.md` in that path's parent folders.

## ADR shape

One file per decision, never edited after it is accepted; a newer ADR replaces
it and says so. In an existing ADR folder, follow its format and numbering.
Otherwise use `docs/adr/NNNN-<short-slug>.md`, numbered from `0001`:

```markdown
# NNNN. <Decision, as a short statement>

Date: YYYY-MM-DD
Replaces: <ADR number, or "none">

## Context
<The forces at play and what made a decision necessary.>

## Decision
<What was decided, stated as the rule.>

## Alternatives
<Each real alternative and why it was not chosen.>

## Consequences
<What becomes easier, what becomes harder, and what is now committed to.>
```

The `DECISIONS.md` entry for an ADR links the newest ADR on the subject only;
a replaced ADR stays in the folder as history and is no longer linked.

## The pointer line

A repository with `DECISIONS.md` adds one line to its agent instructions file
(`CLAUDE.md`, `AGENTS.md` or the equivalent), so agents working there read it
without being told:

```markdown
- **Decisions in force live in [`DECISIONS.md`](DECISIONS.md).** Read the area covering a path before changing it, and add or edit an entry in the same pull request when a change settles something future work must respect.
```

Its two triggers are the whole contract: **read before changing a covered
path**, and **write in the same pull request** that settles something. When
the decisions live in an adopted document instead, the line names that
document.
