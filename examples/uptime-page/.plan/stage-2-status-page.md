# S2 — Status page

<!-- This stage's flags (depends / mode / exec / model / effort) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.

## Goal

Render a list of check results into the single static `public/index.html` —
the user-facing artifact of the whole project — and expose it from the CLI.

## Steps

- [ ] `render(results) -> str` using `string.Template`: overall banner
  (all up / N down), one row per check, UTC generation timestamp.
- [ ] `write_page(results, path="public/index.html")` helper (creates the
  directory if missing).
- [ ] Wire into the CLI as a `--write-page` flag; default CLI behavior stays
  exactly as S1 built it.
- [ ] Tests: golden-file comparison in `tests/test_render.py` for a mixed
  pass/fail result set.

<!-- Checkboxes are the resume mechanism: a session that stops mid-stage marks
the row `doing`, ticks the boxes it finished, and writes a handoff note in the
ledger. Re-running the stage resumes from the first unticked box. -->

## Acceptance

- `uptime-page --config checks.toml --write-page` exits `0` and produces
  `public/index.html` containing one row per configured check.
- `python -m pytest tests/test_render.py -q` passes.

## Artifacts

`uptime/render.py`, `tests/test_render.py`, the `--write-page` flag in
`uptime/cli.py`, generated `public/index.html`. No secrets involved.
