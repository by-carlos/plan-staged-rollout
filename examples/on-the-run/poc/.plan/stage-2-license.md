# S2 — License choice

**`gate: human`.** This stage is never fired unattended. The orchestrator must
refuse it, report the refusal, and hand back; the maintainer then runs it
interactively; the orchestrator resumes afterwards and carries on to SF.

The gate is real, not decorative: choosing a license is a decision with legal
consequences that binds every later user of the code, and nothing in the plan
tells a session which one the maintainer wants. It is exactly the class of
question a run with nobody watching must not answer for itself.

Depends on S0.

## Steps

- [ ] **Ask the maintainer which license this repository ships under.** Do not
      infer it from the ecosystem, from what similar repositories use, or from
      a default. If there is nobody to ask, stop — that is the gate working.
- [ ] Add `LICENSE` with the maintainer's chosen text, with the copyright year
      and holder as they give them.
- [ ] Add a `## License` section to `README.md` naming the choice, and set the
      matching `license` field in `pyproject.toml`.
- [ ] Record in the ledger notes block **who** chose, **what** they chose, and
      that the choice was asked for rather than assumed.

## Acceptance

- [ ] `LICENSE` exists on the stage branch and names the chosen license.
- [ ] `python -c "import tomllib;print(tomllib.load(open('pyproject.toml','rb'))['project']['license'])"`
      prints the same choice; output pasted into the ledger as evidence.
