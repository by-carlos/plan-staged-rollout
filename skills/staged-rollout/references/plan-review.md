# Plan review — lenses, digest and outcomes

How a new plan is reviewed before stage 1 runs. `/plan-stages` runs the review
after decomposition and brief generation, against the **uncommitted**
scaffold: the lens findings are applied first, and only then is the scaffold
committed — so "reviewed before stage 1" holds by construction, with no extra
stage. The review's record lives in `PLAN.md` › Plan review; the brief shows
which lenses ran and why.

**Who gets one.** Only work big enough for a plan — roughly four or more
sessions, the line `SKILL.md` *When NOT to use it* already draws. Work handled
as a single issue is small: its acceptance criteria are the spec, and it gets
no brief and no review. Tiny work has no ticket at all. Within a plan, depth
scales by what the plan touches (the triggers below), never by stage count.

## The four lenses

| Lens | On when | Reads for | Model |
|---|---|---|---|
| **Simplicity** | Always, for every plan. | Stages, steps or decisions that could be cut, merged or deferred; a heavier mechanism where a lighter one meets the requirements; work no requirement asks for. | Sonnet |
| **Architect** | The plan touches **two or more components**, or **changes an interface** (an API, a file format, a CLI, a schema, a contract another component reads). | Wrong boundaries, missing or circular `depends` edges, two stages writing the same file in one wave, a decision that contradicts the requirements, an interface change with no stage updating its consumers. | the bootstrap session's model |
| **Security / red team** | The plan touches **authentication, input handling, secrets, network access, or dependencies**. | Trust boundaries crossed without a check, secrets reaching a committed file or a log, unvalidated input, new dependencies taken on unexamined, an abuse path no stage closes. | the bootstrap session's model |
| **Operator** | The **product** runs unattended or pages someone — a scheduled job, a service, an alert. Not the plan's own stages running unattended. | How it fails, who notices and how, how it is restarted or rolled back, what it logs, what a person must do at 3 a.m. and whether any stage writes that down. | Sonnet |

**Evaluating the triggers.** Bootstrap reads the confirmed requirements and
every stage file's `## Artifacts` section, and turns a lens on when any
trigger matches either. The brief lists each lens that is on with the trigger
that fired it ("Security — stage 3 adds a token to the runner config"). The
user can add or drop lenses in the same single batch of questions as the
**Needs you** decisions; there is no separate ask. That batch comes before
decomposition, so it can only judge triggers against the requirements; once
the stage files exist, the triggers are checked again against their
`## Artifacts`, and a lens that only turns on then is added and shown in the
brief, not asked about. At most four lenses run.

## Running a lens

One subagent per lens, run in parallel, each on the model in the table. Each
gets the uncommitted `.plan/` (`PLAN.md`, every stage file, `BRIEF.md`) and its
row of the table above as its brief, and writes its findings to its own file
in the scratchpad — never to the main thread. Every finding has this shape:

```markdown
- **Where:** PLAN.md › Frozen decisions › D-3  (or: stage-2-<slug>.md › Steps, step 4)
  **Problem:** <what is wrong, in one or two sentences>
  **Change:** <the edit to the plan that fixes it>
```

**The finding rule.** A finding without a plan location **and** a proposed
change is dropped — "consider security" points at nothing and changes nothing.
A lens that finds nothing says so in one line; that is a valid result.

## The digest

The main thread reads **one merged digest of at most ~40 lines**, never the
lens files themselves. Merging drops findings that break the finding rule,
folds duplicates across lenses into one (naming both lenses), and orders what
is left by how much of the plan it would change. If more than ~40 lines
survive, the least consequential findings are cut from the digest and counted
in its last line ("7 minor findings not shown — see the lens files").

## Three outcomes

Every finding in the digest gets exactly one:

- **Change the plan** — edit `PLAN.md` or the stage file it points at, then
  regenerate `BRIEF.md`.
- **File a follow-up** — work outside this plan's scope; record the issue
  reference.
- **Accept with a reason** — leave the plan as it is and say why in one
  clause.

Outcomes the frozen decisions settle are applied without asking. A finding
that would change a **Needs you** decision, or that turns on taste, cost or
something external, is put to the user — all such findings together in one
ask, each with a recommended outcome — before the scaffold is committed. A
finding that reaches the digest is never silently dropped.

## The record

`PLAN.md` › Plan review holds the review's record: the date, the lenses that
ran with the trigger that fired each, and one line per digest finding with
its outcome — the location changed, the follow-up's reference, or the reason
it was accepted. The lens files themselves are scratch and are not committed.

## Cost

The review's subagent tokens count toward the bootstrap's own effort-log row,
so the planning overhead can be read off the log after a real plan. The
target is under ~15% of a plan's sessions; it is a target, not a gate. The
caps — four lenses, a ~40-line digest — are what keep it there.
