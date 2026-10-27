<!-- programme-format: 1 -->
# `PROGRAMME.md` — the programme index

A **programme** is a run of plans for work that has several outcomes, each of
which can merge into `main` on its own. Each outcome is its own plan and lands
through that plan's normal final PR; nothing merges "in parts" inside one plan.
This file defines the one index that ties the plans together. It is not a
template: the bootstrap copies `templates/*.md` into every plan, and this index
belongs at the repository root, not in a plan.

## When a programme exists

`/plan-stages` proposes one when the confirmed requirements hold **two or more
outcomes that can each merge into `main` on their own**. That is a count of
outcomes, not of stages — the stage count is not known until the work is
decomposed, and it is not a size metric. The proposal is a **Needs you**
decision in the bootstrap batch; the user may decline and get one plan.

## Where it lives

A tracked `PROGRAMME.md` at the repository root. The first plan creates it in
its scaffold commit, so it reaches `main` with that plan's final PR; each later
plan branches from `main` and finds it there.

## Shape

```markdown
<!-- programme-format: 1 -->
# Programme: <what the programme delivers, in a few words>

1. **<outcome, in the user's words>** — `plan-<slug>`
2. **<outcome>** — `plan-<slug>`
3. **<outcome>** — `plan-<slug>`
```

- One numbered line per plan, **in running order**. The first line is always
  the next plan to run.
- Each line carries the outcome in plain words and a **pointer**: the plan
  branch name, followed by the final PR's URL once one is open. A plan not yet
  bootstrapped has its intended slug as the pointer.
- **No state column.** Whether a plan is scaffolded, running or in review is
  already held by its own ledger and PR; a copy here is what drifts.

## Lifecycle

| Event | What happens to `PROGRAMME.md` |
|---|---|
| Programme accepted at bootstrap | The first plan writes the file, one line per plan, and commits it with its scaffold. |
| A later plan is bootstrapped | It reads the file on `main`; its slug is the first line. It does not propose another programme. |
| `/plan-close` of a plan | Removes **that plan's line** in a commit on the plan branch, so the final PR carries the removal. |
| `/plan-close` of the last plan | The file would be empty, so the commit **removes the file**. |

Because each close removes its own line, the next plan is always the first
line, and a repository with no `PROGRAMME.md` has no programme in flight.

## Rules

- The index names plans; it never restates their requirements or decisions.
- A line is removed only by the closeout of the plan it names. A line with no
  matching plan branch is reported, never silently deleted.
- Renumbering the list after a removal is not needed; the order is the only
  thing that matters.
