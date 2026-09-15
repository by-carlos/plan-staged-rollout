# S1 — CLI

Put a console entry point on top of S0's function. Depends on S0; read S0's
ledger notes block before starting.

See `PLAN.md` for the frozen CLI contract and the operating protocol.

## Steps

- [ ] Add `slugify/cli.py` with a `main(argv=None)` that takes positional
      words and `--max-length N`, joins the words with a space, and prints the
      slug.
- [ ] Wire the console script `slugify = "slugify.cli:main"` into
      `pyproject.toml`.
- [ ] Honour the frozen exit codes: `0` with the slug printed, `1` with
      nothing printed when the result is empty.
- [ ] Add `tests/test_cli.py` driving `main` directly for both exit codes and
      for `--max-length`.

## Acceptance

- [ ] `python -m pytest -q` passes (both test files), output pasted into the
      ledger notes block as evidence.
- [ ] `python -m slugify.cli Crème Brûlée` prints `creme-brulee` and exits `0`.
