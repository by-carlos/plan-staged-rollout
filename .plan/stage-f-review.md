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
accumulated and sort each into one of three outcomes. Second, write the
lasting record — the decisions worth keeping, the README, the pointer line —
so what the plan settled survives `.plan/` being deleted at closeout. This
stage writes documentation only; it never writes product code.

## Steps

### Loose ends

- [ ] Read every ledger row's notes end to end; list every loose end, gotcha,
  shortcut, and known gap surfaced across all stages.
- [ ] For each loose end, resolve it into exactly one outcome:
  - **Issue** — work that belongs in its own ticket, including a **dated
    follow-up** for a wait measured in days (D-7: the date goes in the issue
    body). Attended: file it through `create-issue` after the user's yes.
    Unattended: file nothing; record it under a "closeout will list" heading in
    this stage's ledger notes, and `/plan-close` copies it into the final PR
    body.
  - **Later plan** — work for a later plan of the programme (D-1, D-6).
    Unattended: record it under the same "closeout will list" heading.
  - **Accepted, won't fix** — write a one-line reason in the ledger so the
    gap is a decision, not a surprise.
  - **Exception — a fix (D-4).** Never a feature: a fix names the requirement,
    failing Done check or regression it repairs, with the user present and
    saying yes, each with its own verification. Fix stages are titled
    `Fix: …`; keep a `#### Fixes` list in this stage's ledger notes (the
    durable count). At most 3 per plan: a fourth fix is a hard stop in every
    mode. This stage's PR lands what it found: the `Fix:` row placed before
    SF, SF's `depends` extended to it, and SF set back to `todo`. The fix runs,
    then this stage re-runs from the top as a redo, and writes its
    documentation only on a clean pass. Unattended, it records a block
    (*Recording a block*) instead.
- [ ] Confirm no loose end was dropped: every item from the first step maps
  to exactly one of the outcomes above.

### Issue #227 closing walk (this plan's extra)

- [ ] Walk all ten "When this closes" items of #227, as written in PLAN.md ›
  Requirements › Done (not the issue), one by one. Record each as **met** with its evidence (the quoted line, the
  command and its output, or the stage's ledger note) in this stage's ledger
  notes. An item that is not met is a loose end like any other.
- [ ] Criterion 4 (the `delete_branch_on_merge` warning) is met by D-2's
  documented rationale, not by a guard: confirm the docs state why the setting
  is harmless under the one-plan-per-milestone model, and record that as its
  evidence.

### Decision triage

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
  (filed, or listed under "closeout will list" when unattended), a later plan,
  an accepted-won't-fix reason, or a D-4 fix recorded in the `#### Fixes`
  list — paste the resulting list into the ledger notes as evidence.
- Every frozen decision has an outcome in the `#### Kept decisions` list in the
  ledger notes, with how the list was approved, and every entry or ADR on it
  exists at its target path.
- The README describes what the plan built, and the pointer line is present
  whenever a decisions document exists.
- The cold-reader check's questions, answers and fixes are in the ledger
  notes, and its last pass had no misses.
- All ten "When this closes" items of #227 are recorded in the ledger notes as
  met, each with its evidence; criterion 4 cites D-2's documented rationale.

## Artifacts

Any `Fix: …` stage (index row, ledger row and stage file) this review added
under D-4 (none expected); the decisions record it wrote (`DECISIONS.md` at the
repository root, per D-8, and any ADRs); the README it updated; the agent
instructions file (`CLAUDE.md`) that gained the pointer line, if it lacks one.
No product code — this stage writes documentation only.
