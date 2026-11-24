# Risk paths

A **risk path** is a file area where a wrong change is costly, hard to spot, or
hard to reverse. This file is the only place the list is defined. The tier
rubric in the skill's *Flag heuristics* reads it: a stage whose `## Artifacts`
name a risk path moves up one tier. Other readers (the plan review, for one)
point here rather than keeping their own copy.

## How a stage is matched

- Only the backticked paths in a stage's `## Artifacts` are read. The section
  stays free prose; nothing about its format changes.
- A path matches when its name or one of its folders plainly belongs to an
  area below. Judge by what the file is, not by a single word in its name:
  `auth_test.py` is a test, not authentication code.
- **Never a risk path, whatever the name:** documentation (`*.md`, `docs/`),
  tests (`tests/`, `test_*`, `*_test.*`, `*.spec.*`, fixtures) and lockfiles
  (`package-lock.json`, `poetry.lock`, `Cargo.lock` and the like).

## The areas

- **Authentication and security:** authentication, crypto, permissions,
  tokens, secrets (`auth/`, `crypto/`, `permissions.py`, `secrets.*`, token
  handling).
- **Data:** migrations, schema files, SQL, ORM schema directories
  (`migrations/`, `schema.sql`, `*.sql`, `prisma/`, `alembic/`).
- **API contracts:** OpenAPI, protobuf, GraphQL schemas, public interface or
  type-declaration files (`openapi.yaml`, `*.proto`, `*.graphql`, `*.d.ts`,
  a package's public `__init__.py` or `index.ts`).
- **Deploy and infrastructure:** CI workflow files, Dockerfiles, Terraform,
  Helm, Kubernetes manifests, service and timer units (`.github/workflows/`,
  `Dockerfile`, `*.tf`, `charts/`, `k8s/`, `deploy/`).
- **Concurrency:** locks, queues, workers, schedulers (`worker.py`,
  `queue/`, `scheduler.*`, cron and timer definitions).

## Extending the list

The list is a starting point. A plan adds its own areas in its `PLAN.md`, as a
`Risk paths:` line under the stage index naming the extra paths or folders and
why they are risky (for example `Risk paths: billing/ — money moves`). A plan
never removes an area from this list.
