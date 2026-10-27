# Fixture: a proof of concept that is drifting — plan & protocol

Proves whether the team's nightly export can be streamed instead of batched,
and ends in a go/no-go decision. Used to exercise the scope referee
(*Adding a stage*); it is not a runnable plan.

## Requirements

- **Outcome:** a go/no-go decision, with evidence, on streaming the nightly
  export instead of batching it.
- **Day to day:** the operator reads the decision record once; nothing runs
  in production.
- **Constraints, ranked:** (1) no change to the production export; (2) at
  most a week of effort.
- **Out of scope:** building or deploying the streaming pipeline;
  migrating consumers.
- **Done, as checks:** a decision record exists with throughput and failure
  numbers from the prototype.

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort | gate |
|---|---|---|---|---|---|---|---|
| S0 Prototype stream reader | `stage-0-prototype.md` | — | direct | inline | sonnet | medium | auto |
| S1 Measure throughput | `stage-1-measure.md` | S0 | direct | inline | sonnet | medium | auto |
| S2 Retry on dropped connections | `stage-2-retry.md` | S1 | direct | inline | sonnet | medium | auto |
| S3 Back-pressure for slow consumers | `stage-3-backpressure.md` | S2 | direct | inline | sonnet | medium | auto |
| S4 Write the decision record | `stage-4-decision.md` | S3 | direct | inline | sonnet | medium | auto |
| SF Plan review | `stage-f-review.md` | S4 | direct | inline | sonnet | medium | auto |

Plan flags: `merge: manual` · `plan-dir: delete`

### Adding a stage — the scope referee

See the plugin's `templates/PLAN.md`, *Adding a stage*.
