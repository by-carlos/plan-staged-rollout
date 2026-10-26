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

- [x] Read every ledger row's notes end to end; list every loose end, gotcha,
  shortcut, and known gap surfaced across all stages.
- [x] For each loose end, resolve it into exactly one outcome:
  - **New stage in this plan** — add a **PLAN.md stage index row** (with its
    `depends` / `mode` / `exec` / `model` / `effort` / `gate` flags — the index is the
    authoritative home, so `/stage-run`'s weight check and next-runnable logic
    can see the stage), a ledger row, and a stage file; it runs later as a
    normal stage in its own fresh session and branch.
  - **Spin-off candidate** — record it in the ledger and note it for the
    final PR body as follow-up; it does not block closeout.
  - **Accepted, won't fix** — write a one-line reason in the ledger so the
    gap is a decision, not a surprise.
- [x] Confirm no loose end was dropped: every item from the first step maps
  to exactly one of the three outcomes above.

### Decision triage

- [x] **Find the target.** Adopt what the repository already has, per the
  spec's *Where it lives*: an existing ADR folder takes the ADRs, an existing
  current-decisions document takes the entries, and `DECISIONS.md` at the
  repository root is created only when neither exists. If `PLAN.md`'s
  requirements or frozen decisions already record the target, use it. When
  the choice is ambiguous, it joins the batch below as one more question —
  unattended, it is a hard stop for this step only: record it as a loose end
  and write no decisions.
- [x] **Propose an outcome for every frozen decision** in `PLAN.md`, applying
  the spec's keep rule (kept when someone could plausibly undo it unknowingly,
  when it took a spike, review or real alternatives to settle, or when the code
  does not make it obvious): **drop**, **an entry** in the target, or **an
  ADR** (which also gets an entry linking it). The fixed protocol entries —
  the git strategy, worktree strategy and final review stage — belong to the
  method, not the project: leave them out. Write each proposal as one line:
  decision id, outcome, target path, and for an entry or ADR the rule as it
  will read.
- [x] **Get the list approved — in one batch.** Attended: put the whole list to
  the user in a single ask, recommended outcomes first, and apply their
  answer. Unattended: apply your own proposals; the list goes into the
  plan→main PR body at closeout, and merging that PR is the approval.
- [x] **Write the approved outcomes**, to the spec's shapes: entries under the
  area whose `Paths:` cover them (adding an area when none does), ADRs in the
  target folder's own format and numbering. Edit or delete an existing entry
  a decision replaces — never mark it superseded.
- [x] **Record the list in this stage's ledger notes** under a heading that
  reads exactly `#### Kept decisions`, one line per frozen decision:
  `<id> — <drop | entry | ADR> — <target path, or the reason it was dropped>`,
  then one line saying how it was approved (`approved by <who> on <date>`, or
  `applied unattended — merging the plan→main PR approves it`). Closeout
  copies this list into the plan→main PR body.

### README, pointer line and cold reader

- [x] **Update the README** — the repository's, or the module's own doc when
  the plan changed one module — so it describes what the plan built: how to
  use it, how to test it, where its parts live. Only what a reader needs once
  `.plan/` is gone; no stage history.
- [x] **Add the pointer line** to the repository's agent instructions file
  (`CLAUDE.md`, `AGENTS.md` or the equivalent), worded as in the spec's *The
  pointer line* and naming the adopted document when that is the target. Skip
  it when the file already carries one, or when the triage kept nothing and
  no decisions document exists.
- [x] **Run the cold-reader check.** Dispatch a fresh subagent with only the
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

- Every loose end captured from the ledger is either a new stage (a PLAN.md
  stage index row **plus** a ledger row **plus** a stage file) or explicitly
  closed (spin-off note or accepted-won't-fix reason) — paste the resulting
  list into the ledger notes as evidence.
- Every frozen decision has an outcome in the `#### Kept decisions` list in the
  ledger notes, with how the list was approved, and every entry or ADR on it
  exists at its target path.
- The README describes what the plan built, and the pointer line is present
  whenever a decisions document exists.
- The cold-reader check's questions, answers and fixes are in the ledger
  notes, and its last pass had no misses.

## Artifacts

No new stages (every loose end closed as a spin-off or accepted). The
decisions record: `DECISIONS.md` (new, at the repository root) and
`docs/adr/0001-dedupe-by-stable-entry-key.md`. `README.md` updated to describe
the job, its configuration and its tests. `CLAUDE.md` gained the pointer line.
No product code — this stage writes documentation only.
