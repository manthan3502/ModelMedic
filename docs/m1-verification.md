# M1 — Dataset Upload, Validation & Project Setup

Status: **PASS**. Verified 2026-10-04 in the Windows-host Docker Desktop Linux
environment. Scope ends at training confirmation. No preprocessing or model is fitted.

## Executed checks

`./scripts/m1-gate.ps1` completed from repository source. It executes the entire
M0 regression gate and the M1 smoke against four real Compose services:

| Check | Result |
|---|---|
| Compose config, locked image build and stack startup | PASS |
| Explicit Alembic upgrade and compatible readiness | PASS |
| Ruff check / format check | PASS |
| mypy | PASS — 30 source files |
| pytest, including real PostgreSQL integration tests | PASS — 66 tests, no skips |
| ESLint | PASS |
| TypeScript | PASS |
| Vitest / React Testing Library | PASS — 8 tests |
| Production frontend build | PASS |
| M0 service/queue smoke | PASS |
| M1 setup smoke through Compose-internal frontend hostname/proxy | PASS |
| npm audit | PASS — zero vulnerabilities |
| scripts.privacy_check and manual diff review | PASS |
| Four locked files compared with starting commit 8e2029a | PASS — unchanged |
| M2 scope review | PASS — no training, split, fitting, metrics or later analysis |

The only test warning is the existing Starlette TestClient/httpx deprecation.
There are no failing or pending gate commands. Earlier occupied verification
ports were resolved by using separate ports; no Docker requirement was skipped.

## Services and migrations

Compose project: `modelmedic-m1-verified`.

- frontend: running, loopback port 15177; same-origin API proxy verified.
- api: running and healthy, loopback port 18004; live/ready endpoints verified.
- worker: running, recent independent heartbeat, actual validation jobs completed.
- postgres: healthy PostgreSQL 17; private network and persistent volume.

Schema head is `0002_m1`, following preserved revision `0001_m0`. Integration
tests create and migrate a fresh disposable PostgreSQL database on each full run.
ORM/migration agreement and M0-row preservation across downgrade/upgrade pass.
Neither API nor worker migrates on startup.

## M1 acceptance criteria

| Required workflow criterion | Result |
|---|---|
| Create project | PASS |
| Upload baseline CSV | PASS |
| Validate using DATASET_VALIDATE worker | PASS |
| Build canonical Parquet with stable row IDs | PASS |
| Review dataset profile | PASS |
| Select eligible target | PASS |
| Select positive class when binary | PASS |
| Configure included features and valid type overrides | PASS |
| Review deterministic preprocessing | PASS |
| Select classifier and weighting | PASS |
| Reach training confirmation | PASS |
| Complete flow without training any model | PASS |

The real smoke uploads a generated in-memory CSV using HTTP chunked transfer,
waits for the live PostgreSQL worker, checks canonical hash/version/row IDs,
configures a binary target and positive class, reviews unfitted preprocessing and
checks all three classifiers with both weighting modes. Counts of model artifacts
and baseline snapshots do not increase. Its project is deleted after verification.

Browser verification independently created and uploaded a generated CSV, reviewed
profile warnings, checked binary-positive-class enforcement and disabled datetime
inputs, reviewed preprocessing, selected Logistic Regression/Balanced and reached
confirmation. The training button remained disabled. Refresh preserved the setup.
Mobile checks at 320px confirmed no page-level horizontal overflow, contained
table scrolling, responsive menu navigation and route focus restoration.

## Validation and security evidence

- Actual streamed bytes enforce the upload cap without trusting Content-Length.
  Oversized uploads leave no dataset/job or temporary file.
- Original paths and canonical attempt paths are server-generated. A hostile
  filename header does not enter storage keys. Private objects are write-once.
- Original integrity is verified before parsing. Canonical SHA-256 and schema
  metadata persist with profile/report and the fenced terminal job transaction.
- Parser tests cover missing-token consistency, reserved/duplicate/empty headers,
  malformed CSV, bad encoding, null bytes, row/column/byte limits and stability.
- Profile tests cover retained duplicates, constants, missingness, likely IDs,
  low-cardinality numeric warnings, literal missing-like strings, whitespace
  distinctions, datetime/free-text and category limits.
- Target tests cover binary/multiclass support, 100-per-class guardrails, missing
  labels, one/>10 classes, continuous outcomes, structured/multilabel cells and
  whitespace normalization without class merging. Discrete numeric labels remain valid.
- Configuration tests cover positive class, classifier/weight restrictions,
  feature inclusion/type validity, duplicate/target inputs, encoded estimates and
  stale dataset IDs. Re-upload invalidates prior configuration.
- Active-job/non-draft/deletion guards and recoverable artifact deletion pass.
  Expired ownership cannot update validation stages or finalize results.
- M0 concurrent claims, active duplicates, lease renewal, stale recovery,
  fencing, heartbeat, readiness and artifact-store regression tests still pass.
- React renders cells as escaped text; script-like preview content is tested.
  Logs/error envelopes do not expose raw parser errors, rows or credentials.
- Existing read-only guard denies every added mutation route. No demo seeding,
  public deployment, authentication or later analytical feature is introduced.
- Commit candidates exclude .env, datasets, model/database artifacts, caches,
  screenshots, generated builds, personal addresses and credentials.

## Implementation choices

The existing synchronous SQLAlchemy/API/worker architecture is extended rather
than replaced. Frequently queried project selections use normal columns; nested
feature selections, ordered classes and normalization metadata use draft JSONB.
Canonical strings preserve lexical categories and nullable missing values;
uint64 ordinal row IDs preserve order and uniqueness. Numeric conversion and all
learned preprocessing remain outside M1. Exact import/serialization rules are in
the README. Actual held-out support is explicitly deferred to the M2 split.

No locked-specification conflict was found. No M2 work was begun. The single
milestone commit uses `feat: add baseline dataset setup and validation workflow`;
its hash, push and clean-tree verification are included in the final milestone report.
