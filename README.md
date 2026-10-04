# ModelMedic

ML Reliability & Drift Analysis Platform for classical tabular classification.
ModelMedic is designed to distinguish data, prediction, confidence and measured
performance changes. Data drift alone does not establish predictive degradation.

## Current status

**M3 — Monitoring Core + Mode A.** Establish an immutable baseline, create a
monitoring run, validate an unlabeled current CSV and inspect separate data,
missingness, prediction and confidence evidence. Current performance/calibration,
errors and slices remain explicitly unavailable without labels. Stop before M4.

The four [locked specifications](docs/specs/) remain unchanged. Scientific
implementation details are documented in [methodology](docs/methodology.md).

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
$env:MM_CODE_VERSION = (git rev-parse HEAD).Trim()
$env:MM_CODE_DIRTY = if (git status --porcelain) { 'true' } else { 'false' }
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
No production deployment is part of M3.

`docker compose down` stops this stack while retaining the database and artifact
volumes. Do not remove volumes containing data you need.

## Complete M3 verification (including M0, M1 and M2 regressions)

```powershell
./scripts/m3-gate.ps1
```

The gate builds and explicitly migrates the four-service `modelmedic-m3-verified`
stack (API 18006, frontend 15179), runs all scientific/PostgreSQL/backend/frontend
checks, and exercises all 12 binary/multiclass × classifier × weighting
combinations through the real frontend proxy and leased worker. It verifies
training, artifacts, establishment and immutability, then binary/multiclass Mode A
validation, drift, predictions, confidence and immutable reloads. Synthetic smoke projects
are removed using test-only cleanup; no product unlock route exists.

The PostgreSQL tests create and migrate a uniquely named disposable database,
then remove only that database. The supplied connection needs CREATEDB. A run
without TEST_DATABASE_URL skips integration tests and is not a complete gate.
The Compose test override supplies the connection automatically.

The M0/M1 gate scripts remain regression entry points. The M1 flow still stops
at confirmation without training; M2 enables training only after explicit action.
After the executable gate, run `uv run python scripts/privacy_check.py`, inspect
the diff and locked files, and complete browser verification before committing.

Services remain running for inspection. To stop without deleting data:

```powershell
docker compose -p modelmedic-m3-verified down
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

For host API/worker development, set `MM_CODE_VERSION` and `MM_CODE_DIRTY` as
above, and set `MM_DATABASE_URL` to a reachable
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
backend/app/science/ Deterministic split, pipeline, metrics, calibration and importance
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
check (at least 20 per class) is enforced during M2 training before fitting.

Draft re-upload clears configuration. Active validation jobs block mutation and
deletion; established projects cannot be changed by baseline mutation routes. Deletion removes the
entire project artifact prefix and cascades metadata/jobs. An external deletion
failure leaves `deletion_pending` for retry and blocks other changes. No new public
demo/deployment features are added; the existing fail-closed guard covers all routes.

## Baseline training and locking

Each leased BASELINE_TRAIN execution creates an attempt snapshot. No scientific
work runs inside an HTTP request or while holding the queue claim transaction.
Results and the terminal job transition publish in the same ownership-fenced
transaction. Artifact keys include the snapshot ID and cannot be overwritten.

Changing a trained draft requires explicit discard confirmation. Establishment
requires a TRAINED snapshot with the current dataset/configuration fingerprint,
and atomically freezes it with the project. Existing baseline-changing APIs
then return 409. A different baseline requires a new project.

The manifest records Git SHA, dirty/clean build state, source-content digest,
scientific versions and artifact SHA-256. Rebuild after committing to stamp
new training attempts with the final commit; historical manifests never change.
Only the worker loads internally generated joblib artifacts, after integrity,
format, Python-minor and exact scikit-learn checks.


## Unlabeled monitoring workflow (M3)

Open an established project → New monitoring run → Details → Upload current CSV
→ Compatibility review → Mode A declaration → Analyze current data → Saved results.
The worker applies the exact frozen baseline snapshot, without fitting or retraining.
Required features must be present; extras are allowed, shown and ignored for the
model. Frozen numeric columns must contain only missing or safely numeric values;
categorical values are never silently trimmed or re-inferred. Minimum 50 rows.

Data / Feature Detail compare raw observations with all valid baseline rows.
Predictions / Confidence use the immutable M2 held-out reference. Distribution and
missingness tests share one BH family; prediction/confidence comparisons remain
separate. Every chart has numerical evidence and a table. Published outputs retain
bins, shares, test membership, hashes, snapshot and code/methodology provenance.

Complete valid labels identify Mode B, but M3 does not analyze labeled outcomes.
Partial or unknown labels block validation; they never silently become Mode A.
No severity score, accuracy degradation claim or automatic retraining instruction
is generated. Run history preserves monitoring-date/timestamp/ID ordering.

The executable gate runs all M0–M2 regressions, all M3 scientific/PostgreSQL/frontend
checks and binary/multiclass real-stack monitoring smoke tests. Browser, privacy,
locked-specification and Git checks are recorded in [M3 verification](docs/m3-verification.md).
