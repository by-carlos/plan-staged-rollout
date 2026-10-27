# Fixture: build and live stages — plan & protocol

Fixture for the session-start hook (`hooks/session-start`). It holds build
(`auto`) and live stages and one row with a gate value no runner knows, so the
hook's output can be checked for the runnable set, the one-live-at-a-time note
and the refusal of the unknown value. It is not a real plan: copy it to a
scratch directory, `git init` there and run the hook from that directory (the
hook resolves the plan root with `git rev-parse --show-toplevel`, so running it
inside this repository would read this repository's `.plan/`).

## Stage index & dependencies

| Stage | File | Depends | mode | exec | model | effort | gate |
|---|---|---|---|---|---|---|---|
| S0 Scaffold the service | `stage-0-scaffold.md` | — | direct | inline | sonnet | high | auto |
| S1 Build the API | `stage-1-build-api.md` | S0 | direct | inline | sonnet | high | auto |
| S2 Deploy to staging | `stage-2-deploy-staging.md` | S0 | direct | inline | sonnet | high | live |
| S3 Migrate the production data | `stage-3-migrate-data.md` | S0 | direct | inline | sonnet | high | live |
| S4 Warm the cache | `stage-4-warm-cache.md` | S0 | direct | inline | sonnet | medium | canary |
| S5 Write the runbook | `stage-5-runbook.md` | S1 | direct | inline | sonnet | medium | auto |
| SF Plan review | `stage-f-review.md` | S2, S3, S4, S5 | direct | inline | opus | high | auto |

Plan flags: `merge: manual` · `plan-dir: delete`
