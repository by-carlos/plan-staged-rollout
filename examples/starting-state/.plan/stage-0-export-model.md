# S0 — Export model

<!-- This stage's flags (depends / mode / exec / model / effort / gate /
estimate) live ONLY in the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Requirements › Outcome and Out of scope, Frozen
> decisions, Operating protocol) and `.plan/LEDGER.md`. Follow the protocol,
> including the finish protocol: this stage ends when its Acceptance passes.

## Goal

Add the export model the CSV writer (S1) and the CLI flag (S2) both build on:
one `ExportRow` per invoice, with amounts kept exact until they are written.

## Steps

- [x] Record the starting state: before changing anything, run each command in
  Frozen decisions › starting state on the commit this stage branch starts
  from, and fill LEDGER.md › S0 › Starting state with the commit, each
  command's result (pass, fail or skip) and the real output tail. Fix nothing
  that fails here.
- [x] Define `ExportRow` (frozen dataclass: `number`, `customer`, `issued`,
  `due`, `total` as `Decimal`).
- [x] Implement `rows_for(invoices)` in `invoice/export.py`.
- [x] Tests in `tests/test_export_model.py`.

## Acceptance

- The *Starting state* block in `LEDGER.md` lists every command in Frozen
  decisions › starting state with a result.
- `python -m pytest -q` shows no failure beyond the starting state's, and the
  new tests in `tests/test_export_model.py` pass.
- `ruff check .` passes.

## Artifacts

`invoice/export.py`, `tests/test_export_model.py`, `.plan/LEDGER.md`. No
secrets involved.
