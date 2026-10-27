# SF — Plan review

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md` — the *entire* ledger, every note, gotcha, shortcut, and
> known gap. This is the one stage exempt from the read-scope rule: read
> everything, not just what this stage depends on. Follow the protocol,
> including the finish protocol.
>
> Also read the `DECISIONS.md` format spec, `decisions-format.md`:
> `.plan/decisions-format.md` when the plan carries a copy, otherwise the
> plugin's `skills/staged-rollout/references/decisions-format.md`. It defines
> the keep rule, the entry and ADR shapes, where the record lives and the
> pointer line — this file does not restate them.

## Goal

Close the plan out twice over. First, catalog every loose end the plan
accumulated and sort each into one of the outcomes below. Second, on a clean
pass only, write the lasting record — the decisions worth keeping, the README,
the pointer line — so what the plan settled survives `.plan/` being deleted at
closeout. This stage writes documentation only; it never writes product code,
and it never adds a stage — the one exception is a capped, user-approved
**fix** (below).

## Steps

### Loose ends

- [ ] Read every ledger row's notes end to end; list every loose end, gotcha,
  shortcut, and known gap surfaced across all stages.
- [ ] Read `PLAN.md` › Requirements › Out of scope as well: a **dated
  follow-up** recorded there at bootstrap (a wait measured in days, which is
  never a stage) is a loose end to list here.
- [ ] For each loose end, resolve it into exactly one outcome:
  - **Issue** — work that belongs in its own ticket, including a **dated
    follow-up** for a wait measured in days. A dated follow-up's body states
    the **date**, the **exact check** to make, the **pass condition** (with
    the basis for its threshold) and the **action on failure**; nothing is
    scheduled. Attended: file it through `create-issue` after the user's yes.
    Unattended: file nothing; record it under a `closeout will list` heading
    in this stage's ledger notes, and `/plan-close` copies it into the final
    PR body.
  - **Later plan** — work for a later plan of the programme (the programme
    index, `PROGRAMME.md` at the repository root, names it). Unattended:
    record it under the same `closeout will list` heading.
  - **Accepted, won't fix** — write a one-line reason in the ledger so the
    gap is a decision, not a surprise.
  - **Exception — a fix.** Never a feature. A fix names the requirement,
    failing Done check or regression it repairs, and is made only with the
    user present and saying yes, each with its own verification. Fix stages
    are titled `Fix: …`; keep a `#### Fixes` list in this stage's ledger notes
    — one line per fix — because it is the durable count. **At most 3 per
    plan: a fourth fix is a hard stop in every mode.**
    - *How a fix runs.* This stage's own PR lands what it found, so the
      catalogue of loose ends is kept: the `Fix:` stage passes the scope
      referee (`PLAN.md`, *Adding a stage*), then its index row is placed
      **before SF** (a new stage has an index row, a ledger row and a stage
      file under an unused plain ID; run the plugin's
      `skills/staged-rollout/scripts/renumber_stages.py --slug <slug>`, so the
      numbers stay in running order and SF stays last), SF's `depends` extended to it, and
      SF's row set back to `todo`. The fix runs as an ordinary stage; this
      stage then re-runs **from the top** as a redo.
    - *Documentation waits.* A pass that adds a fix writes none of the
      Decision triage and README steps below — they run only on a clean pass,
      the redo that finds nothing to fix.
    - *Unattended.* Unattended, this stage stops and asks: it records a block
      through the plan's *Recording a block* path instead of adding the fix.
- [ ] Confirm no loose end was dropped: every item from the first step maps
  to exactly one of the outcomes above.

### Decision triage

Runs only on a clean pass — no fix added by this run of the stage. If the
loose-end step added a fix, skip this section and the next, record the fix and
stop at the finish protocol.

- [ ] **Find the target.** Adopt what the repository already has, per the
  spec's *Where it lives*: an existing ADR folder takes the ADRs, an existing
  current-decisions document takes the entries, and `DECISIONS.md` at the
  repository root is created only when neither exists. If `PLAN.md`'s
  requirements or frozen decisions already record the target, use it. When
  the choice is ambiguous, it joins the batch below as one more question —
  unattended, it is a hard stop for this step only: record it as a loose end
  and write no decisions.
- [ ] **Propose an outcome for every frozen decision** in `PLAN.md`, applying
  the spec's keep rule (kept when someone could plausibly undo it unknowingly,
  when it took a spike, review or real alternatives to settle, or when the code
  does not make it obvious): **drop**, **an entry** in the target, or **an
  ADR** (which also gets an entry linking it). The fixed protocol entries —
  the git strategy, worktree strategy and final review stage — belong to the
  method, not the project: leave them out. Write each proposal as one line:
  decision id, outcome, target path, and for an entry or ADR the rule as it
  will read.
- [ ] **Get the list approved — in one batch.** Attended: put the whole list to
  the user in a single ask, recommended outcomes first, and apply their
  answer. Unattended: apply your own proposals; the list goes into the
  plan→main PR body at closeout, and merging that PR is the approval.
- [ ] **Write the approved outcomes**, to the spec's shapes: entries under the
  area whose `Paths:` cover them (adding an area when none does), ADRs in the
  target folder's own format and numbering. Edit or delete an existing entry
  a decision replaces — never mark it superseded.
- [ ] **Record the list in this stage's ledger notes** under a heading that
  reads exactly `#### Kept decisions`, one line per frozen decision:
  `<id> — <drop | entry | ADR> — <target path, or the reason it was dropped>`,
  then one line saying how it was approved (`approved by <who> on <date>`, or
  `applied unattended — merging the plan→main PR approves it`). Closeout
  copies this list into the plan→main PR body.

### README, pointer line and cold reader

Clean pass only, as above.

- [ ] **Update the README** — the repository's, or the module's own doc when
  the plan changed one module — so it describes what the plan built: how to
  use it, how to test it, where its parts live. Only what a reader needs once
  `.plan/` is gone; no stage history.
- [ ] **Add the pointer line** to the repository's agent instructions file
  (`CLAUDE.md`, `AGENTS.md` or the equivalent), worded as in the spec's *The
  pointer line* and naming the adopted document when that is the target. Skip
  it when the file already carries one, or when the triage kept nothing and
  no decisions document exists.
- [ ] **Run the cold-reader check.** Dispatch a fresh subagent with only the
  repository, told never to open `.plan/`, and ask it at least: *how do I
  test this*, *where is \<a part the plan built\>*, and *why \<a decision the
  triage kept\>*. Name real parts and decisions from this plan. Every
  question it answers wrongly or cannot answer is a gap in the README or the
  decisions record: fix it in this stage, then ask again until it answers.
  Record the questions, its first answers and what was fixed in the ledger
  notes.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- Every loose end captured from the ledger has exactly one outcome: an issue
  (filed, or listed under `closeout will list` when unattended — a dated
  follow-up carrying its date, exact check, pass condition and action on
  failure), a later plan, an accepted-won't-fix reason, or a fix recorded in
  the `#### Fixes` list (never more than 3) — paste the resulting list into
  the ledger notes as evidence.
- A pass that added a fix wrote no decisions entry, README change or pointer
  line. On a clean pass, the rest of this list holds:
- Every frozen decision has an outcome in the `#### Kept decisions` list in the
  ledger notes, with how the list was approved, and every entry or ADR on it
  exists at its target path.
- The README describes what the plan built, and the pointer line is present
  whenever a decisions document exists.
- The cold-reader check's questions, answers and fixes are in the ledger
  notes, and its last pass had no misses.

## Artifacts

<Any `Fix: …` stage (index row, ledger row and stage file) this review added,
none expected; the decisions record it wrote (`DECISIONS.md` or the adopted document, and any
ADRs); the README or module doc it updated; the agent instructions file that
gained the pointer line. No product code — this stage writes documentation
only.>
