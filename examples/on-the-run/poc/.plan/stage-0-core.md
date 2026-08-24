# S0 — Slug core

Land `slugify(text, *, max_length=None)` and its tests. First stage: it cuts
its branch from the plan branch tip with nothing upstream of it.

See `PLAN.md` for the frozen behaviour of `slugify` and for the operating
protocol this stage follows. Nothing here restates either.

## Steps

- [ ] Add `pyproject.toml`: name `slugify-poc`, Python 3.12, no runtime
      dependencies, `pytest` as a dev extra. No console script yet — that is
      S1's, and adding it here would leave S1 nothing to land.
- [ ] Add `slugify/__init__.py` re-exporting `slugify` from `slugify.core`.
- [ ] Add `slugify/core.py` implementing the frozen normalisation rules.
- [ ] Add `tests/test_core.py` covering: plain ASCII, accented input
      (`"Crème Brûlée"` → `"creme-brulee"`), punctuation runs collapsing to a
      single `-`, leading/trailing separators stripped, empty input and
      all-punctuation input both returning `""`, and `max_length` truncating
      at a `-` boundary rather than mid-word.

## Acceptance

- [ ] `python -m pytest tests/test_core.py -q` passes, output pasted into the
      ledger notes block as evidence.
- [ ] `python -c "from slugify import slugify; print(slugify('Crème Brûlée!!'))"`
      prints `creme-brulee`.
