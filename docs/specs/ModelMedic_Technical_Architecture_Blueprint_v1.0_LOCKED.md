# ModelMedic — Technical Architecture Blueprint

**Version:** 1.0  
**Status:** **LOCKED after independent architecture audit**  
**Project:** ModelMedic — ML Reliability & Drift Analysis Platform  
**Purpose:** Define the engineering architecture before UI/UX design and implementation.

---

## 1. Architecture Summary

ModelMedic V1 uses a deliberately simple but strong architecture:

- **Frontend:** React + TypeScript + Vite
- **Backend API:** FastAPI
- **Background ML execution:** Dedicated Python worker process
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy 2.x
- **Migrations:** Alembic
- **ML/Data:** scikit-learn, Pandas, NumPy, SciPy
- **Job queue:** PostgreSQL-backed jobs table
- **Local artifact storage:** Filesystem / Docker volume
- **Production artifact storage:** Private S3-compatible object storage
- **Model persistence:** Internal joblib artifact + manifest + SHA-256 + environment metadata
- **Canonical dataset format:** Parquet
- **Containers:** Docker + Docker Compose
- **CI:** GitHub Actions
- **Preferred portfolio deployment direction:** Railway or another Docker + PostgreSQL + private-object-storage provider
- **Public deployment mode:** Read-only safe demo mode

High-level topology:

```text
                    ┌─────────────────────────┐
                    │       React + TS        │
                    │        Frontend         │
                    └────────────┬────────────┘
                                 │ REST
                                 ▼
                    ┌─────────────────────────┐
                    │        FastAPI          │
                    │      API / Web App      │
                    └─────────┬───────┬───────┘
                              │       │
                  metadata    │       │ files/artifacts
                              ▼       ▼
                    ┌────────────┐  ┌────────────────┐
                    │ PostgreSQL │  │ Artifact Store │
                    └──────┬─────┘  └───────┬────────┘
                           │                 │
                         jobs                │
                           ▼                 │
                    ┌─────────────────────────┐
                    │    Python ML Worker     │
                    │ validation / training   │
                    │ drift / metrics         │
                    │ calibration / slices    │
                    └─────────────────────────┘
```

This remains one monorepo and one backend codebase. The API and worker are separate processes, not separate microservices.

---

## 2. Architecture Principles

1. **Scientific rules belong in backend ML modules, never in React.**
2. **Monitoring data can never refit preprocessing or retrain the frozen baseline model.**
3. **HTTP request lifetime must not control long-running ML jobs.**
4. **PostgreSQL stores structured metadata/results, not raw uploaded CSV blobs.**
5. **Datasets and ML artifacts use durable artifact storage.**
6. **Historical results are versioned and never silently recomputed.**
7. **No enterprise infrastructure without a clear V1 need.**
8. **Public portfolio deployment must be safe without requiring a full account system.**

---

## 3. Why PostgreSQL

Use PostgreSQL in both development and deployment.

Reasons:

- project/run relationships
- worker + API concurrent access
- transactional job claiming
- structured result history
- deletion cascades
- JSONB only where nested analysis output is appropriate
- avoids a later SQLite-to-PostgreSQL migration

No SQLite fallback is required.

---

## 4. Background Worker

Baseline training and monitoring analysis must not run inside long HTTP requests.

Flow:

```text
Frontend requests training/analysis
        ↓
FastAPI validates request and creates job
        ↓
202 Accepted + job id
        ↓
Worker claims job
        ↓
Worker performs ML/statistical work
        ↓
Results persisted atomically
        ↓
Frontend polls job state
```

The worker runs the same backend codebase using a worker entrypoint.

---

## 5. Why No Celery / Redis / Kafka

V1 does not need:

- Celery
- Redis
- RabbitMQ
- Kafka

Use a PostgreSQL-backed job table.

The worker claims work using transaction-safe row locking such as `FOR UPDATE SKIP LOCKED`.

Benefits:

- durable jobs
- fewer services
- easy local Docker setup
- simpler interview explanation
- enough capacity for a portfolio-grade batch application

---

## 6. Job Types

```text
DATASET_VALIDATE
BASELINE_TRAIN
MONITORING_ANALYZE
SLICE_ANALYZE
```

Internal job states:

```text
QUEUED
RUNNING
SUCCEEDED
FAILED
```

Jobs also store a human-readable stage.

Example baseline stages:

```text
VALIDATING
SPLITTING
CROSS_VALIDATING
TRAINING
EVALUATING
CALIBRATION
IMPORTANCE
PERSISTING
COMPLETE
```

Example monitoring stages:

```text
VALIDATING
PREDICTING
DATA_DRIFT
MISSINGNESS
PREDICTION_DRIFT
CONFIDENCE
PERFORMANCE
CALIBRATION
PERSISTING
COMPLETE
```

Do not display fake percentages unless a mathematically meaningful percentage exists.

---

## 7. Job Safety, Leasing and Idempotency

The PostgreSQL jobs table is the complete V1 queue.

Required job fields include:

```text
id
job_type
target_type
target_id
params JSONB
state
stage
attempt
max_attempts
lease_expires_at
heartbeat_at
error_code
error_message
created_at
started_at
finished_at
```

### Claiming

The single worker claims one eligible `QUEUED` job in a short transaction using row locking such as:

```text
FOR UPDATE SKIP LOCKED
```

The transaction is committed immediately after the claim.

No database transaction remains open during ML computation.

### Lease / heartbeat

When a worker claims a job it receives a lease.

The worker updates `heartbeat_at` / `lease_expires_at` periodically.

If a lease expires:

- the job may be requeued once when `attempt < max_attempts`
- after the allowed retry is exhausted, it becomes `FAILED` with a sanitized `WORKER_LOST`-style error
- deterministic failures such as validation errors or model non-convergence are not retried automatically

Recommended V1:

```text
max_attempts = 2
```

### Duplicate prevention

Only one active (`QUEUED` or `RUNNING`) job of the same job type may exist for the same target.

A duplicate train/analyze request returns:

```text
409 Conflict
```

### Atomic finalization / fencing

Scientific computation may happen outside a DB transaction.

Final persistence happens in one transaction:

1. verify this worker still owns the active job attempt
2. verify the target project/run is still in a state that permits finalization
3. write all final result rows
4. update the run/project state
5. mark the job `SUCCEEDED`

If the ownership/fencing update affects zero rows, the transaction rolls back.

This prevents stale/zombie workers from publishing duplicate results.

Result endpoints do not expose a monitoring run as final until the run state is `ANALYZED`.

### Deletion

Deletion is synchronous in V1, not a background job.

Before deletion:

- refuse with `409` while an active job exists for the target
- set project/run deletion state where needed to prevent new job claims/finalization
- delete artifact objects
- delete database rows transactionally where possible
- retries must safely resume cleanup

Project-prefix artifact deletion is used to clean related/orphaned objects.

---

## 8. Repository Structure

```text
modelmedic/
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   ├── pages/
│   │   ├── routes/
│   │   ├── hooks/
│   │   ├── types/
│   │   └── utils/
│   ├── tests/
│   ├── package.json
│   └── package-lock.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── domain/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── ml/
│   │   │   ├── validation/
│   │   │   ├── preprocessing/
│   │   │   ├── training/
│   │   │   ├── metrics/
│   │   │   ├── drift/
│   │   │   ├── calibration/
│   │   │   ├── importance/
│   │   │   ├── slices/
│   │   │   └── reporting/
│   │   ├── jobs/
│   │   ├── storage/
│   │   └── main.py
│   └── tests/
│       ├── unit/
│       ├── scientific/
│       ├── integration/
│       └── api/
│
├── migrations/
├── docs/
│   ├── methodology.md
│   ├── architecture.md
│   └── limitations.md
├── scripts/
├── compose.yaml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

---

## 9. Backend Boundaries

### API layer
HTTP parsing, request validation, authorization/demo-mode checks, response shaping.

### Service/application layer
Project lifecycle, job creation, orchestration, storage coordination.

### ML domain layer
Scientific computations only.

### Persistence layer
SQLAlchemy repositories/models and transactions.

### Storage layer
Dataset/model/report artifact access.

The API layer must not contain ML calculations.

---

## 10. ML Package Responsibilities

### `validation/`
- CSV validation
- schema compatibility
- target/class checks
- sample guardrails
- frozen feature-type validation

### `preprocessing/`
- sklearn pipeline construction
- numeric median imputation
- categorical missing handling
- one-hot encoding
- logistic-regression scaling

### `training/`
- stratified split
- cross-validation
- fitting
- frozen class ordering

### `metrics/`
- binary metrics
- multiclass metrics
- undefined-metric rules
- probability metric class-order handling

### `drift/`
- KS
- Wasserstein
- Jensen-Shannon
- chi-square
- Fisher exact missingness test
- Benjamini-Hochberg correction

### `calibration/`
- reliability bins
- Brier
- Log Loss
- support guardrails

### `importance/`
- permutation importance on raw project features through the full pipeline

### `slices/`
- exploratory labeled slice analysis

### `reporting/`
- deterministic reviewed templates only

---

## 11. Dataset Storage

Do not store raw CSV content in PostgreSQL.

For each upload store:

- original uploaded CSV
- canonical validated Parquet representation
- metadata in PostgreSQL

Suggested hierarchy:

```text
projects/
  <project_id>/
    baseline/
      original.csv
      canonical.parquet
      model/
        pipeline.joblib
        manifest.json
    runs/
      <run_id>/
        original.csv
        canonical.parquet
```

Original CSV preserves the submitted input.
Canonical Parquet preserves the validated typed representation used internally.

---

## 12. Artifact Store Abstraction

Define an `ArtifactStore` interface.

Implementations:

### Development
`LocalArtifactStore`

### Deployment
`S3ArtifactStore`

ML and service code should use the interface rather than provider-specific APIs.

---

## 13. Model Persistence

Persist the complete fitted sklearn pipeline:

```text
pipeline.joblib
```

Do not store user-supplied serialized models.

Beside it store:

```text
manifest.json
```

Manifest fields include:

```text
artifact_version
methodology_version
code_version
project_id
target
positive_class
feature_names
feature_types
baseline_class_list
class_order
classifier
class_weighting
random_seed
python_version
scikit_learn_version
numpy_version
scipy_version
pandas_version
artifact_sha256
created_at
```

---

## 14. Artifact Loading Rules

Before loading:

1. fetch trusted artifact reference from database
2. fetch private object
3. compute SHA-256
4. compare stored hash
5. validate artifact format version
6. check critical runtime/library compatibility
7. load only if checks pass

Known incompatibility:

> block load and return an artifact compatibility error

Do not silently load a model in an incompatible environment.

---

## 15. Core Database Entities

Recommended relational entities:

```text
projects
datasets
project_features
baseline_snapshots
model_artifacts
monitoring_runs
run_feature_results
run_metrics
run_prediction_results
run_calibration_results
run_error_results
slice_analyses
slice_results
jobs
```

Use normal columns for frequently queried values.
Use JSONB only for naturally nested outputs such as calibration bins or category lists.

---

## 16. `projects`

Key fields:

```text
id
name
description
state
target_column
positive_class
problem_type
classifier
class_weight_mode
random_seed
methodology_version
created_at
updated_at
baseline_established_at
```

Locked baseline fields become immutable after establishment.

---

## 17. `datasets`

Key fields:

```text
id
project_id
run_id nullable
role: BASELINE | CURRENT
original_object_key
canonical_object_key
sha256
row_count
column_count
uploaded_at
canonical_sha256
profile JSONB
validation_report JSONB
```

`monitoring_runs.dataset_id` points to the run's current dataset; `datasets` does not point back to a run, avoiding a circular foreign key.

Baseline snapshots reference their baseline dataset explicitly.

---

## 18. `project_features`

One row per frozen baseline feature:

```text
id
project_id
feature_name
feature_type
included
category_count
baseline_summary JSONB
```

Numeric summary may include:

```text
missing_count
missing_rate
min
max
quantiles
```

Categorical summary may include:

```text
missing_count
missing_rate
category_counts
```

---

## 19. `baseline_snapshots`

Each row represents one concrete baseline training attempt.

```text
id
project_id
dataset_id
status: TRAINED | ESTABLISHED
config_fingerprint
development_count
heldout_count
split_seed
split_membership_object_key
heldout_reference_object_key
cv_summary
class_counts
heldout_class_counts
baseline_metrics_version
created_at
established_at
```

`config_fingerprint` hashes the exact baseline input/configuration:

- dataset hash
- target
- positive class
- included features
- frozen feature types
- classifier
- class weighting

`Establish Baseline` succeeds only when:

- the selected snapshot is `TRAINED`
- its fingerprint still matches the current DRAFT configuration

Establishment flips the snapshot/project state atomically.

Artifact/object keys include `snapshot_id` and are write-once.

A retrain while still in `DRAFT` invalidates/discards the previous unestablished snapshot and its artifact prefix.

All baseline mutation routes pass through one service-layer lifecycle guard and return `409` after establishment.

---

## 20. `model_artifacts`

```text
id
project_id
storage_key
sha256
artifact_version
methodology_version
code_version
environment_manifest JSONB
created_at
```

---

## 21. `monitoring_runs`

```text
id
project_id
dataset_id
baseline_snapshot_id
name
monitoring_date
notes
mode: A | B
state
methodology_version
code_version
row_count
validation_warnings JSONB
created_at
analyzed_at
```

History ordering:

1. monitoring date
2. creation timestamp
3. run id

---

## 22. `run_feature_results`

One row per feature per run:

```text
run_id
feature_name
feature_type
distribution_status
statistic_name
statistic_value
raw_p_value
adjusted_p_value
distance_name
distance_value
baseline_valid_n
current_valid_n
baseline_missing_rate
current_missing_rate
missing_rate_delta
missing_test_name
missing_p_value
missing_adjusted_p_value
range_outside_rate
new_categories JSONB
disappeared_categories JSONB
warnings JSONB
```

---

## 23. `run_metrics`

```text
run_id
scope: OVERALL | CLASS
class_label nullable
metric_name
baseline_value nullable
current_value nullable
delta nullable
status
reason nullable
baseline_support
current_support
```

---

## 24. Prediction Results

Store:

```text
baseline_class_shares
current_class_shares
js_distance
test_name
p_value
baseline_n
current_n
baseline_confidence_mean
current_confidence_mean
baseline_confidence_median
current_confidence_median
confidence_ks
confidence_p
```

Always keep the frozen baseline class order.

---

## 25. Calibration Results

Store per overall/class calibration:

```text
run_id
class_label nullable
status
reason
baseline_n
current_n
baseline_bins JSONB
current_bins JSONB
warnings JSONB
```

Each bin:

```text
count
mean_predicted_probability
observed_frequency
```

---

## 26. Error Results

Store aggregates and source indices, not copies of full rows:

```text
confusion_matrix
false_positive_count
false_negative_count
common_confusion_pairs
example_row_indices
```

At display time fetch at most 50 example rows from canonical data.

---

## 27. Slice Storage

`slice_analyses`:

```text
id
run_id
feature_name
created_at
```

`slice_results`:

```text
slice_analysis_id
slice_value
row_count
class_support JSONB
metrics JSONB
status
reason
```

Slice analyses are additive derived outputs and never rewrite core run results.

---

## 28. REST API

Base path:

```text
/api/v1/
```

Project resources:

```text
POST   /projects
GET    /projects
GET    /projects/{id}
DELETE /projects/{id}
```

Baseline flow:

```text
POST /projects/{id}/baseline/upload
PUT  /projects/{id}/configuration
POST /projects/{id}/train
POST /projects/{id}/establish
```

Baseline results:

```text
GET /projects/{id}/baseline/summary
GET /projects/{id}/baseline/metrics
GET /projects/{id}/baseline/calibration
GET /projects/{id}/baseline/importance
```

Monitoring:

```text
POST   /projects/{id}/runs
GET    /projects/{id}/runs
GET    /runs/{id}
POST   /runs/{id}/upload
POST   /runs/{id}/analyze
DELETE /runs/{id}
```

Results:

```text
GET /runs/{id}/summary
GET /runs/{id}/features
GET /runs/{id}/features/{feature}
GET /runs/{id}/metrics
GET /runs/{id}/predictions
GET /runs/{id}/calibration
GET /runs/{id}/errors
```

Slices:

```text
POST /runs/{id}/slices
GET  /runs/{id}/slices
GET  /runs/{id}/slices/{slice_id}
```

Jobs:

```text
GET /jobs/{id}
```

Report:

```text
GET /runs/{id}/report
```

---

## 29. Standard API Error Envelope

```text
code
message
details
request_id
```

Never return Python stack traces to clients.

---

## 30. Deterministic Reporting

Reports use fixed reviewed templates with computed values substituted.

No LLM.
No free-form generated scientific interpretation.

V1 report format:

- print-friendly HTML
- browser Print → Save as PDF if needed

Do not add a server-side PDF engine unless later justified.

---

## 31. Missing-Value Parsing

Recommended V1 parsing:

Automatically missing:

- empty CSV cell
- whitespace-only cell

Do **not** automatically reinterpret literal strings such as:

```text
NA
N/A
None
null
unknown
?
```

They remain literal values unless a later explicit import policy is approved.

Use the same rule for baseline and current uploads.

---

## 32. Frozen Feature Semantics

Current uploads never re-infer semantic feature types.

Baseline categorical → current values interpreted as categories.

Baseline numeric → current non-missing values must be safely numeric/coercible, otherwise block.

---

## 33. Drift Input Boundary

Distribution drift must operate on raw observed values before preprocessing.

Numeric:

- non-missing raw values
- before median imputation
- before scaling

Categorical:

- non-missing raw categories
- before missing-category insertion
- before one-hot encoding

Missingness is analyzed separately.

---

## 34. Categorical Statistical Test

Deterministic algorithm:

1. use raw observed non-missing category counts
2. let `n_base` and `n_current` be the valid sample sizes
3. compute  
   `t = 5 × (n_base + n_current) / min(n_base, n_current)`
4. pool categories with combined baseline+current count below `t` into reserved internal bucket `__MM_OTHER__` for the test only
5. if the pooled bucket would still have an expected cell below 5, merge it into the smallest retained test category
6. require at least 2 resulting test categories
7. build the 2×K contingency table
8. require every expected cell ≥5
9. if valid → chi-square
10. otherwise → `INSUFFICIENT DATA`

Persist the test-time pooling membership with the feature result.

Raw user categories remain visible and unchanged.

Jensen-Shannon remains descriptive where calculable.

---

## 35. Missingness Statistical Test

Create a 2×2 table:

```text
             Missing  Observed
Baseline
Current
```

If both missing counts are zero:

- status = `NOT DETECTED`
- no p-value
- exclude from BH family

Otherwise:

- all expected cells ≥5 → chi-square
- any expected cell <5 → Fisher exact

Valid p-values enter the BH family.

---

## 36. BH/FDR Family

One run's BH family contains only:

- valid feature distribution p-values actually calculated
- valid missingness p-values actually calculated

Exclude:

- `INSUFFICIENT DATA`
- skipped tests
- no-p-value cases

Apply Benjamini-Hochberg with `q = 0.05`.

Prediction drift and confidence tests remain separate.

---

## 37. Frozen Probability Class Order

The baseline class list and order are persisted and used for every probability-based calculation:

- predict_proba column mapping
- Log Loss
- Brier
- ROC-AUC
- calibration

Never infer probability class order from a current run.

---

## 38. Calibration

Quantile bins:

```text
40–99   → 3
100–249 → 5
250–499 → 8
500+    → 10
```

Binary/OvR requirement:

```text
≥20 positive
≥20 non-positive
```

For labeled support `<250`, show a limited-support calibration warning.

Every bin displays its `n`.

---

## 39. Permutation Importance

Run permutation importance against the complete sklearn pipeline using the original held-out feature columns.

Do not calculate primary importance on one-hot-expanded dummy columns.

Configuration:

```text
scoring = balanced_accuracy
n_repeats = 10
random_state = 42
```

Negative values remain negative and are not clipped.

---

## 40. Resource Limits

Initial configurable defaults:

- CSV size: 25 MB max
- rows: 50,000 max
- input columns: 100 max
- included modelling features: 50 max
- categories/model feature: 100 max
- encoded columns after preprocessing: 2,000 max

These are computational resource limits, not scientific rules.

---

## 41. Public Demo Mode

Do not build a full authentication system for V1.

### Full Mode
For local/private use:
- uploads
- training
- monitoring
- deletion

### Public Demo Mode
For portfolio URL:
- seeded public/synthetic projects
- read-only exploration
- no uploads
- no training
- no destructive operations

Mutation restrictions must be enforced server-side, not only hidden in React.

Public Demo Mode is **fail-closed**:

- default-deny all non-GET application routes
- allow only explicitly safe read/health routes
- the application refuses to start in a non-local environment unless an explicit deployment mode is configured
- CI/tests enumerate routes and verify that mutation methods return `403` in Demo Mode
- demo data is seeded by running the real ModelMedic pipeline through a documented seed command, never by hand-authoring analysis results
- when methodology version changes, the demo fixture must be regenerated

A public read-only demo deployment does not require the ML worker service.

---

## 42. Security

- treat CSV uploads as untrusted
- sanitize filenames; never trust client paths
- artifact object keys are server-generated
- no public artifact buckets
- no secrets in Git
- dataset cell content rendered as text, never raw HTML
- no raw rows in logs
- no credentials in logs
- no user-supplied joblib/pickle model files
- verify artifact hash/version before load
- destructive endpoints disabled in public demo mode

---

## 43. Local Docker

Compose services:

```text
frontend
api
worker
postgres
```

Plus a shared local artifact volume.

---

## 44. Production Deployment

Provider-neutral application design.

Preferred initial portfolio direction:

```text
Web/API service
Worker service
Managed PostgreSQL
Private S3-compatible bucket
```

Railway is a suitable candidate, but application code must not depend on Railway-specific storage/database APIs.

---

## 45. Frontend Architecture

Use:

- React
- TypeScript
- Vite
- React Router
- TanStack Query

Do not add Redux unless later UI design proves it necessary.

Frontend calculates no scientific statistics.

---

## 46. Logging

Structured logs.

Use:

- `request_id` for HTTP
- `job_id` for background work

Never log raw uploaded rows.

---

## 47. Versioning

Store separately:

### `methodology_version`
Changes when scientific methodology changes.

### `code_version`
Git commit SHA.

Historical runs retain both.

---

## 48. Testing Strategy

### Scientific/unit
- split determinism
- leakage prevention
- metrics
- KS
- Wasserstein
- JS
- chi-square validity
- Fisher exact switching
- BH correction
- missingness
- calibration bins
- probability class order
- permutation importance

### Mode A
Assert:
- drift/prediction/confidence available
- no performance
- no calibration
- no confusion matrix
- no forbidden claims

### Mode B
Test:
- binary
- multiclass
- absent classes
- undefined metrics
- class ordering
- calibration
- slices
- error analysis

### Integration
Use real PostgreSQL.

Test end-to-end:
- create project
- upload baseline
- train
- establish
- Mode A
- Mode B
- history
- report
- deletion

### Frontend
- Vitest
- React Testing Library

### Browser E2E
- Playwright
- baseline flow
- Mode A
- Mode B
- report flow

### Docker smoke
- build
- start stack
- API readiness
- frontend reachable
- DB connectivity
- worker heartbeat

---

## 49. CI

GitHub Actions gates:

### Backend
- Ruff
- Python type checking
- pytest unit/scientific

### Frontend
- ESLint
- TypeScript check
- Vitest
- production build

### Integration
- PostgreSQL
- API/worker integration tests

### Container
- Docker build
- Compose smoke test

### Repository security
- secret scanning

No deployment after failed gates.

---

## 50. Database Migrations

Use Alembic.

Every production schema change must have a migration.

Do not mutate production schema automatically from ORM metadata at application startup.

---

## 51. Health Checks

API:

```text
/api/v1/health/live
/api/v1/health/ready
```

`live` = process alive.

`ready` = database reachable + critical config valid.

Worker maintains heartbeat information.

---

## 52. Deletion

Deleting a project must cascade through:

- monitoring runs
- slice analyses
- analysis result rows
- jobs
- dataset metadata
- artifact metadata

and remove corresponding:

- original CSVs
- canonical Parquet files
- model artifacts
- manifests

No intentional orphaned artifacts.

---

## 53. Explicitly Rejected Infrastructure

No:

- Redis
- Celery
- Kafka
- RabbitMQ
- Kubernetes
- microservices
- GraphQL
- MLflow
- feature store
- model registry
- distributed computation
- separate drift service
- real-time monitoring

---

## 54. Architecture Gate

Before implementation, architecture passes only if:

- PRD rules map cleanly to modules
- monitoring can never refit/retrain the frozen baseline
- API and worker roles are clear
- long jobs outlive HTTP requests safely
- job/result persistence is idempotent
- raw datasets are not stored as DB blobs
- datasets/artifacts have durable storage
- artifact integrity/versioning is defined
- baseline probability class order is frozen
- scientific tests are first-class
- public portfolio mode cannot mutate/upload
- no unnecessary distributed infrastructure exists

---

## 55. Baseline Reference Persistence

Monitoring must never need to recompute historical baseline model behaviour.

At baseline training time persist an immutable held-out reference Parquet artifact containing:

```text
__mm_row_id
y_true
y_pred
probability columns in frozen class order
confidence
```

Persist split membership in a companion artifact or the same baseline snapshot artifact set.

Also persist baseline:

- performance metrics
- calibration bins/metrics
- permutation-importance mean/std

Monitoring runs always record the exact `baseline_snapshot_id` used.

Feature drift reads the immutable baseline canonical Parquet as the full raw drift reference.

Display summaries in PostgreSQL are not treated as the scientific source of truth.

---

## 56. Dataset Validation Job

Add:

```text
DATASET_VALIDATE
```

Upload flow:

1. stream upload to a server-controlled temporary file
2. enforce byte limit while streaming, not only via `Content-Length`
3. queue validation/profile job
4. parse/validate
5. assign stable internal row ids using reserved `__mm_` namespace
6. write canonical Parquet
7. persist `profile` and `validation_report`
8. expose baseline configuration/current-run mode only after validation succeeds

Re-upload is allowed only while the relevant project/run is still mutable.

---

## 57. Canonical Parquet Contract

Canonical datasets contain:

- stable `__mm_row_id`
- frozen user columns
- target where supplied
- deterministic dtypes
- standard null representation

Store:

```text
canonical_sha256
canonical_schema_version
```

Reserved internal columns use the `__mm_` prefix.

A user upload containing a conflicting reserved column name is rejected.

---

## 58. Ordered Class Data

Never rely on JSON object key order for class-sensitive results.

Persist the frozen class list once.

Per-class arrays use that exact order, or store ordered arrays of:

```json
{"label": "...", "value": ...}
```

Applies to:

- prediction shares
- class support
- probability vectors
- confusion matrices
- class metrics

The positive-class probability column is always:

```text
class_order.index(positive_class)
```

never an assumed fixed column number.

---

## 59. Immutable Plot Data

The worker precomputes plot-ready scientific data during analysis.

Examples:

- numeric histograms using shared baseline-derived bin edges
- ordered categorical share tables
- confidence histograms
- calibration bins

These plot data are persisted with results so the API does not recalculate statistics and old visualizations do not change after code upgrades.

Example/error rows remain source-row references into canonical Parquet.

---

## 60. Immutable Reports

At run finalization generate a structured deterministic report payload and persist it with:

```text
report_template_version
```

Historical reports therefore do not change merely because wording templates change later.

Slice sections may be rendered from separately versioned additive slice results.

The wording audit tests backend-generated report payloads.

---

## 61. Compute-Budget Gate

The configured limits are initial defaults, not guaranteed capacity.

Before implementation milestones lock performance expectations, benchmark worst-case representative workloads for all three classifiers, especially Gradient Boosting.

The benchmark determines deployment-safe:

- max rows
- max included features
- max encoded columns
- per-job wall-clock timeout
- worker memory target

Thread counts must be explicit (for example BLAS/OpenMP environment limits).

The missing category is counted when estimating encoded dimensionality.

Changing these computational caps after benchmark does not change product scope or scientific methodology.

---

## 62. Deployment Mechanics

- API and worker use the same immutable container image/code build.
- Only the worker process loads `joblib` model artifacts.
- Exact scikit-learn version and Python minor version must match the artifact compatibility policy.
- All Python and frontend dependencies use committed lockfiles.
- Alembic runs exactly once as an explicit migration/pre-deploy step.
- API/worker do not race to apply migrations.
- Worker refuses to start against an unsupported schema revision.
- Automated deployment must be gated behind passing CI on the protected branch/tag.

---

## 63. Database / Runtime Style

V1 uses synchronous SQLAlchemy and synchronous backend service code.

There is no need to introduce asynchronous database access merely for style.

The background worker handles long computation outside HTTP request lifetime.

---

## 64. Scientific Library Parameters

Pin explicit parameters and dependency versions in `docs/methodology.md`.

At minimum:

```text
scipy.stats.ks_2samp(..., method="auto")
scipy.stats.chi2_contingency(..., correction=False)
scipy.stats.fisher_exact(..., alternative="two-sided")
scipy.stats.false_discovery_control(..., method="bh")
```

The pinned SciPy version is part of the scientific environment lock.

---

## 65. Frontend Serving

Development may use a separate Vite frontend service.

Production uses one origin to avoid unnecessary CORS complexity:

- build React static assets
- serve them from the web/API deployment (or one same-origin reverse proxy)

The separate Compose frontend service is a development convenience, not a required production service.

---

## 66. Worker Health

Persist worker heartbeat in a tiny worker-status record independent of active jobs.

Full-mode readiness can report:

- database healthy
- schema compatible
- recent worker heartbeat

Demo Mode does not require worker readiness.

Project/run read responses may include the current active job summary so the frontend can resume polling after refresh; this is derived from `jobs`, not duplicated as a second authoritative foreign key.

---

## 67. Slice Idempotency

Only one slice analysis exists per:

```text
(run_id, feature_id, methodology_version)
```

A repeat request returns the existing analysis rather than recomputing duplicate derived results.

---

## 68. Category / Header Normalization

Target labels retain the locked PRD rule: safe surrounding-whitespace normalization with no silent class merging.

Categorical feature values are **not silently trimmed or merged** after baseline establishment.

During validation, ModelMedic warns when categories differ only by surrounding whitespace so the user can clean the source before establishing baseline.

Numeric-looking columns containing literal tokens such as `NA`/`N/A` receive a clear validation diagnostic rather than being silently reinterpreted.

Raw CSV headers are never embedded directly in API URLs; stable `feature_id` values are used.

---

## 69. Deletion Semantics

Deletion background job types are removed.

Synchronous deletion:

1. checks for active jobs; if present → `409`
2. prevents new claims/finalization for that target
3. deletes project/run artifact prefix
4. deletes DB rows/cascades
5. leaves a recoverable deletion state if external-object deletion fails

Project deletion removes runs, slices, baseline snapshots, artifacts, datasets and associated result rows.

---

## 70. Architecture Audit Resolution

The independent audit found no need for redesign.

Accepted hardening changes include:

- leased/fenced PostgreSQL job execution
- duplicate active-job prevention
- synchronous deletion
- training-attempt / baseline-snapshot binding
- configuration fingerprints
- persisted held-out prediction/reference artifacts
- run → baseline snapshot binding
- sample-size-aware categorical pooling
- dedicated dataset-validation jobs
- ordered class-value storage
- persisted plot data
- immutable report payloads
- compute benchmark gate
- fail-closed demo mode
- one-shot Alembic migration
- stable feature IDs/internal column namespace
- provider-neutral deployment

The following original architecture choices remain unchanged:

- PostgreSQL in development and deployment
- one backend codebase with API + worker processes
- PostgreSQL queue; no Redis/Celery
- raw datasets outside PostgreSQL
- private artifact storage abstraction
- internal `joblib` pipeline artifacts with integrity/version checks
- Docker/Compose
- read-only public demo mode
- deterministic reports
- explicit rejection of enterprise/distributed infrastructure

# Architecture Status

**STEP 6 — TECHNICAL ARCHITECTURE BLUEPRINT: LOCKED**

The architecture has passed independent audit and the accepted hardening changes are incorporated.

Implementation should not silently alter these architecture decisions.

Next stage:

**STEP 7 — UI/UX + Dashboard Blueprint.**
