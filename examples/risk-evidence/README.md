# Risk evidence — what the plan review reports

A worked case for the *Risk evidence* step of the final review stage
([`stage-f-review.md`](../../skills/staged-rollout/references/templates/stage-f-review.md)).
The risk paths come from
[`risk-paths.md`](../../skills/staged-rollout/references/risk-paths.md); this
example does not restate them.

## The plan, as the review finds it

Three finished stages. Only their `## Artifacts` backticked paths and ledger
notes matter here.

| Stage | `## Artifacts` | Risk path? | Ledger evidence |
|---|---|---|---|
| S1 Orders table | `migrations/0007_orders.sql`, `tests/` | yes — data | `$ python -m orders.migrate --dry-run` → `would apply 0007_orders; 0 rows touched` |
| S2 Session tokens | `auth/tokens.py`, `tests/` | yes — authentication | `$ pytest -q` → `41 passed` (the suite never calls `auth/tokens.py`) |
| S3 Docs | `README.md`, `docs/usage.md` | no — documentation | none needed |

## What the review reports

**S1** has targeted evidence: a migration dry run that exercises the changed
schema. No entry.

**S3** matches no risk path. No entry.

**S2** is the only loose end, because a generic passing suite is not aimed at
the token change:

> **S2 Session tokens** — `auth/tokens.py` (authentication) has no targeted
> check in its notes. Missing: a test of the changed token expiry, or a scan of
> the new token handling. → resolved like any loose end: an issue, accepted
> with a reason, or a `Fix:` stage under the existing cap of 3 with the user
> present.

The loose-end list keeps its usual shape; the review adds no ledger column and
blocks nothing.
