# S0 — Fire evidence

<!-- This stage's flags (depends / mode / exec / model / effort / gate) live ONLY in
the PLAN.md stage index — the single authoritative home. Do not restate them
here; a copy is what drifts. -->

> First read `.plan/PLAN.md` (Frozen decisions + Operating protocol) and
> `.plan/LEDGER.md`. Follow the protocol, including the finish protocol.

## Goal

Record what this session observes about **itself**, so the mechanism that fired
it can be verified from the inside rather than inferred from the request that
was sent. Nothing else — this stage exists to be evidence.

## Steps

- [ ] Create `probe/cloud-fire-evidence.md`.
- [ ] Write into it, as plain text, each of the following, labelled, exactly as
      observed — never as recalled, assumed, or reasoned from this file:
      - the model this session is running as, quoted from your own system
        prompt (the model ID if you have it, otherwise the name as stated);
      - the value of the `CLAUDE_EFFORT` environment variable, read with a
        shell command (`echo "$CLAUDE_EFFORT"`), including the command you ran
        and its literal output — if it is empty, say that it is empty;
      - the value of `CLAUDE_CODE_EFFORT_LEVEL`, read the same way;
      - the branch this container started on (`git rev-parse --abbrev-ref HEAD`
        before you create the stage branch, plus its output);
      - whether the `plan-staged-rollout` plugin's slash commands are available
        to you in this container (say plainly yes or no).
- [ ] Follow `PLAN.md`'s finish protocol: commit, push the stage branch, open
      the stage PR into the plan branch, and update this stage's ledger row and
      notes block with the same observations.

## Acceptance

- `probe/cloud-fire-evidence.md` exists on the stage branch and contains the
  five labelled observations above, each with the command and its literal
  output where a command was used.
- The stage PR is open against the plan branch.

## Artifacts

- `probe/cloud-fire-evidence.md`

No secrets. If any command output would contain a token or credential, write
`<redacted>` in its place and say which command it came from.
