# ModelMedic

ML Reliability & Drift Analysis Platform for classical tabular classification.
ModelMedic is designed to distinguish data, prediction, confidence and measured
performance changes. Data drift alone does not establish predictive degradation.

## Current status

**M0 — Repository + Platform Foundation.** This repository contains the API,
PostgreSQL schema, worker queue, private local artifact store and light-mode
application shell. Project creation, CSV upload, profiling, training, monitoring,
calibration and slices are **not implemented**. No analytical demo data is fabricated.

The four [locked specifications](docs/specs/) are the source of truth. They remain
unchanged; the next milestone is M1 — Dataset Upload, Validation & Project Setup.

## Prerequisites

- Git
- Docker Desktop using Linux containers, with Docker Compose
- PowerShell 7 for the automated gate script (individual Docker commands also work elsewhere)
- For optional host development: Python 3.12, uv 0.11.0+, Node.js 24 and npm

## Start locally

From the repository root, copy `.env.example` to `.env`. Replace the password
placeholder with a random local password consisting of URL-safe letters/digits.
Do not commit `.env`. PostgreSQL is accessible only on the internal Compose network.

```powershell
Copy-Item .env.example .env
# Edit .env and replace the password placeholder before proceeding.
docker compose config --quiet
docker compose build
docker compose up -d --wait postgres
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait
```

The explicit Alembic command runs once before the API and worker start. Neither
process applies migrations automatically. The worker refuses incompatible schemas.
API and worker use the same built image and synchronous SQLAlchemy code.

- Frontend: <http://localhost:5173>
- API liveness: <http://localhost:8000/api/v1/health/live>
- API readiness (database and schema): <http://localhost:8000/api/v1/health/ready>
- Worker heartbeat: <http://localhost:8000/api/v1/health/worker>

The Vite development proxy forwards `/api` to the API, so browser requests remain
same-origin. The Compose frontend is a development service; a production host
must serve the built assets on the API origin, as required by the locked architecture.
No production deployment is part of M0.

`docker compose down` stops this stack while retaining the database and artifact
volumes. Do not remove volumes containing data you need.

## Complete M0 verification

```powershell
./scripts/m0-gate.ps1
```

The script stops on a failed command. It uses the separate Compose project
`modelmedic-m0-gate`, ports 18000/15173, production API/worker images, a test-only
image with the same locked dependencies plus development tools, and real PostgreSQL.
It builds, migrates, starts all services, runs lint/type/tests/build and performs
the end-to-end dummy-job smoke check. It leaves services running for inspection.

The integration suite creates a uniquely named disposable database using
`TEST_DATABASE_URL` as its administrative connection. It migrates that empty
database, verifies ORM/migration agreement and removes **only that test database**.
Its user needs `CREATEDB`. The supplied database is not truncated or dropped.
Tests without `TEST_DATABASE_URL` skip integration tests and **do not constitute
the complete gate**. The Compose override supplies it automatically.

After the executable gate, review privacy, confirm locked specs are unchanged,
inspect the diff/staging, then commit and push the milestone. A passing test suite
alone is not a passing M0 milestone.

To stop the verification stack without removing its data:

```powershell
docker compose -p modelmedic-m0-gate down
```

## Individual checks and host development

```powershell
uv sync --locked
uv run ruff check backend migrations scripts
uv run ruff format --check backend migrations scripts
uv run mypy
uv run pytest
cd frontend
npm ci
npm run lint
npm run typecheck
npm run test
npm run build
npm run dev
```

For host API/worker development, set `MM_DATABASE_URL` to a reachable
`postgresql+psycopg://...` connection, run `uv run alembic upgrade head`, then run
`uv run uvicorn backend.app.main:create_app --factory --no-access-log` and
`uv run python -m backend.app.jobs.worker` in separate terminals. There is no
SQLite fallback. The default Compose database intentionally has no host port.

### Internal dummy-job verification

This command is available only in local full mode. It creates no product feature:

```powershell
docker compose exec api python -m backend.app.jobs.dev
# Read the printed job ID:
# GET /api/v1/jobs/<job-id>
docker compose exec api python -m backend.app.jobs.dev --fail
```

Use `--target <UUID>` to specify an internal target. An active duplicate is
rejected; a terminal job does not prevent a later job. `--fail` produces a
sanitized terminal failure without automatic retry. Lease recovery permits at
most one retry; a second lost lease becomes `FAILED / WORKER_LOST`.

## Repository structure

```text
frontend/          React, Router, TanStack Query, tokens and component tests
backend/app/api/   HTTP boundary reserved for route modules
backend/app/core/  Configuration and structured logging
backend/app/db/    SQLAlchemy models and schema compatibility checks
backend/app/domain/ Job states and errors
backend/app/schemas/ Response contracts
backend/app/services/ Transactional queue services
backend/app/jobs/  Dedicated worker and internal developer command
backend/app/storage/ ArtifactStore protocol and LocalArtifactStore
backend/app/ml/    Placeholder only; no M0 scientific behavior
backend/tests/    Unit and real PostgreSQL integration tests
migrations/       Explicit Alembic revision history
scripts/          Complete gate and Docker smoke verification
docs/specs/       Four immutable specifications
```

## Storage and security boundaries

Artifacts are private, server-keyed objects on a shared Docker volume; raw data
is not stored as PostgreSQL blobs. The local adapter rejects traversal and absolute
paths, publishes complete objects atomically, and refuses overwrites. Its directory
must remain controlled by the service account. The protocol permits a future private
S3-compatible adapter without changing scientific logic.

Local ports bind to loopback. This M0 stack has no authentication and must not be
exposed publicly. Configuration outside local mode requires an explicit deployment
mode. The basic demo guard denies non-GET requests, but full demo functionality
and its product UI remain M6 work. No real datasets or model artifacts ship here.

See [foundation architecture](docs/architecture.md) for queue transaction boundaries
and [M0 verification](docs/m0-verification.md) for the recorded acceptance evidence.
