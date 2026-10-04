# ModelMedic

ML Reliability & Drift Analysis Platform for classical tabular classification.
ModelMedic is designed to distinguish data, prediction, confidence and measured
performance changes. Data drift alone does not establish predictive degradation.

## Current status

**M1 — Dataset Upload, Validation & Project Setup.** Create a draft project,
upload and validate a baseline CSV, inspect its profile, select target/positive
class and feature types, review preprocessing, and select classifier/weighting.
The flow ends at training confirmation. No model or preprocessing is fitted.
Training, metrics, monitoring, calibration and drift are **not implemented**.

The four [locked specifications](docs/specs/) are the source of truth. They remain
unchanged; M2 training and evaluation require a separately authorized milestone.

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
No production deployment is part of M1.

`docker compose down` stops this stack while retaining the database and artifact
volumes. Do not remove volumes containing data you need.

## Complete M1 verification (including M0 regressions)

```powershell
./scripts/m1-gate.ps1
```

The script stops on a failed command. It uses the separate Compose project
`modelmedic-m1-verified`, ports 18004/15177, production API/worker images, a test-only
image with the same locked dependencies plus development tools, and real PostgreSQL.
It builds, migrates, starts all services, runs lint/type/tests/build and performs
the M0 dummy-job smoke check and the real M1 setup smoke through the frontend proxy.
The latter checks all six classifier/weighting combinations, canonical SHA-256,
row IDs and the absence of trained artifacts. It deletes its generated project.
Services remain running for browser inspection.

The integration suite creates a uniquely named disposable database using
`TEST_DATABASE_URL` as its administrative connection. It migrates that empty
database, verifies ORM/migration agreement and removes **only that test database**.
Its user needs `CREATEDB`. The supplied database is not truncated or dropped.
Tests without `TEST_DATABASE_URL` skip integration tests and **do not constitute
the complete gate**. The Compose override supplies it automatically.

After the executable gate, review privacy, confirm locked specs are unchanged,
inspect the diff/staging, then commit and push the milestone. A passing test suite
alone is not a passing milestone. The archived M0 gate remains available as
`./scripts/m0-gate.ps1`; its test commands now also include M1 regressions.

To stop the verification stack without removing its data:

```powershell
docker compose -p modelmedic-m1-verified down
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
backend/app/api/   Project, upload and draft-configuration HTTP boundary
backend/app/core/  Configuration and structured logging
backend/app/db/    SQLAlchemy models and schema compatibility checks
backend/app/domain/ Job states, deterministic CSV/profile/configuration rules
backend/app/schemas/ Response contracts
backend/app/services/ Transactional queue and project services
backend/app/jobs/  Dedicated worker and internal developer command
backend/app/storage/ ArtifactStore protocol and LocalArtifactStore
backend/app/ml/    Placeholder only; no fitted preprocessing or models
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

Local ports bind to loopback. This local stack has no authentication and must not be
exposed publicly. Configuration outside local mode requires an explicit deployment
mode. The basic demo guard denies non-GET requests, but full demo functionality
and its product UI remain M6 work. No real datasets or model artifacts ship here.

See [foundation architecture](docs/architecture.md) for queue transaction boundaries
and the archived [M0 verification](docs/m0-verification.md) for foundation evidence.

## Baseline setup and import contract

Uploads use a raw CSV request body (`Content-Type: text/csv`), streamed to a
server-controlled temporary file. The API counts actual bytes and rejects an
oversized upload before publishing or queueing it. Filenames never determine
storage paths. `DATASET_VALIDATE` runs in the existing leased PostgreSQL worker.
Validation report and profile writes share the fenced job-finalization transaction.

UTF-8 (optional BOM) is supported. Duplicate/empty headers, reserved `__mm_`
headers, malformed row widths/quoting, empty data, unsafe encoding and resource
limit violations produce reviewed diagnostics. Empty and whitespace-only cells
become null. Literal `NA`, `N/A`, `None`, `null`, `unknown` and `?` remain values.
Rows and categorical values are never silently deleted, trimmed or merged.

Canonical Parquet v1 stores uint64 ordinal `__mm_row_id` and nullable Arrow
strings for every user column. Keeping lexical values lossless allows numeric
columns to be configured as categories without merging `001` and `1`. Numeric
semantics are validated during inference/override review; numeric conversion and
learned preprocessing belong to the later fitted pipeline. Original and canonical
SHA-256, canonical schema version, profile and validation report are persisted.
Serialization uses pinned PyArrow 21.0.0, Parquet 2.6, Zstandard, no dictionaries
and no statistics. Revalidating identical bytes produces identical canonical bytes.

Only eligible 2–10-class, fully labeled targets with at least 100 observations
per class can be configured. Binary targets require an explicit positive class.
Safe target-label whitespace normalization is blocked when it would merge labels.
Discrete numeric labels are valid classes; continuous numeric outcomes outside the
class cap and JSON list/object target cells are rejected. Feature inclusion is
explicit; unsupported datetime,
free-text and high-cardinality categorical features are visibly excluded with reasons.
Encoded-column estimates conservatively include one missing bucket per categorical.

Resource defaults are 25 MiB / 50,000 rows / 100 input columns / 50 included
features / 100 categories / 2,000 encoded columns. `MM_*` settings in `.env.example`
configure the computational limits; the UI displays the backend's actual limits.
Pre-split support is enforced now. The authoritative actual held-out support
check (at least 20 per class) is explained at confirmation and remains M2 work.

Draft re-upload clears configuration. Active validation jobs block mutation and
deletion; non-draft projects cannot be changed by M1 routes. Deletion removes the
entire project artifact prefix and cascades metadata/jobs. An external deletion
failure leaves `deletion_pending` for retry and blocks other changes. No new public
demo/deployment features are added; the existing fail-closed guard covers all routes.
