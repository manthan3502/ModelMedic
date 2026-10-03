# ModelMedic — Milestone-by-Milestone Implementation Plan

**Version:** 1.0  
**Status:** Build plan derived from locked PRD, Architecture, and UI/UX Blueprint  
**Project:** ModelMedic — ML Reliability & Drift Analysis Platform  
**Rule:** Do not start the next milestone until the current milestone gate passes.

---

# 1. Build Strategy

ModelMedic will be implemented milestone-by-milestone.

Every milestone must end with:

1. all milestone acceptance criteria satisfied,
2. required automated tests passing,
3. Docker stack healthy where applicable,
4. privacy/security checks passing,
5. documentation updated,
6. working tree clean,
7. exactly one meaningful milestone commit pushed.

No milestone should silently change:

- ML methodology,
- product scope,
- architecture,
- UI/UX decisions.

If implementation exposes a genuine contradiction, stop and report it before changing a locked decision.

---

# 2. Final Milestone Sequence

```text
M0  Repository + Platform Foundation
M1  Dataset Upload, Validation & Project Setup
M2  Baseline Training + Evaluation + Baseline Lock
M3  Monitoring Core + Mode A
M4  Mode B Performance + Calibration + Errors
M5  Feature Diagnostics + Slices + Trends + Reports
M6  Full UI/UX Integration + Public Demo Mode
M7  Hardening, Scientific QA, CI, Deployment
M8  Documentation, Portfolio, Resume & Interview Readiness
```

---

# 3. Milestone M0 — Repository + Platform Foundation

## Goal

Create the full project skeleton and prove that the application architecture works end-to-end before implementing scientific functionality.

## Backend

Create:

- FastAPI application
- SQLAlchemy setup
- PostgreSQL connectivity
- Alembic
- health endpoints
- structured logging
- request IDs
- configuration system
- artifact-storage abstraction
- local artifact store
- worker entrypoint
- PostgreSQL jobs table
- worker heartbeat

## Frontend

Create:

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- base layout
- global top bar
- placeholder Projects page
- base design tokens
- typography
- accessible focus system

## Docker

Create Compose services:

```text
frontend
api
worker
postgres
```

Use a shared local artifact volume.

## Job queue foundation

Implement:

- `QUEUED`
- `RUNNING`
- `SUCCEEDED`
- `FAILED`

Add:

- `attempt`
- `max_attempts`
- `lease_expires_at`
- heartbeat
- `FOR UPDATE SKIP LOCKED`
- duplicate active-job prevention
- basic fencing on finalization

No scientific jobs yet.

## Database entities required in M0

At minimum:

- projects
- datasets
- baseline_snapshots
- model_artifacts
- monitoring_runs
- jobs

Result tables may be introduced later.

## Tests

Backend:

- API health
- DB readiness
- migrations apply cleanly
- job claim locking
- duplicate job prevention
- expired job recovery
- job fencing

Frontend:

- app renders
- top navigation works

Docker:

- all services start
- API ready
- worker heartbeat visible
- PostgreSQL healthy

## Gate M0

PASS only if:

- clean clone can start with Docker Compose,
- migrations run,
- API and worker both reach PostgreSQL,
- frontend reaches API,
- one dummy job can be queued, claimed, completed and observed from API,
- duplicate active dummy job is rejected,
- tests/lint/type checks pass.

## Milestone commit

```text
feat: establish ModelMedic application foundation
```

---

# 4. Milestone M1 — Dataset Upload, Validation & Project Setup

## Goal

Complete the entire pre-training baseline setup workflow.

This milestone ends before real model training.

## Project lifecycle

Implement:

```text
DRAFT
BASELINE_READY
MONITORING
```

Only `DRAFT` behavior is used here.

## Project APIs

Implement:

- create project
- list projects
- fetch project
- delete draft project

## Dataset validation job

Add:

```text
DATASET_VALIDATE
```

Workflow:

```text
upload
→ temporary file
→ validation job
→ canonical Parquet
→ profile
→ validation report
```

## Upload security

Implement:

- byte-limit enforcement during streaming
- server-generated filenames/object keys
- reserved `__mm_` namespace rejection
- duplicate-column rejection
- malformed CSV handling
- safe encoding handling
- no raw user filename in storage path

## Canonical dataset

Generate deterministic Parquet with:

```text
__mm_row_id
validated user columns
target when present
```

Store:

- canonical SHA-256
- schema version

## Validation rules

Implement:

- row/column count
- duplicate rows
- target candidates
- target class counts
- target eligibility
- missingness
- inferred numeric/categorical types
- constant columns
- high missingness warning
- likely identifiers
- low-cardinality numeric warning
- unsupported datetime/text warning
- categorical cardinality
- whitespace-differing categorical values
- numeric-looking values with literal missing-like strings

## Missing-value policy

Apply the locked consistent parser.

Do not silently reinterpret arbitrary literal strings as missing.

## Feature configuration

Implement:

- target selection
- positive class selection
- include/exclude
- numeric/categorical override where valid
- encoded-column estimate
- feature IDs

## Preprocessing review

Backend exposes deterministic preprocessing summary.

Frontend implements:

- preprocessing explanation page
- leakage explanation
- frozen-pipeline explanation

## Model configuration

Allow exactly:

- Logistic Regression
- Random Forest
- Gradient Boosting

Weighting:

- Standard
- Balanced

No training yet.

## UI screens

Complete:

- Projects
- Create Project
- Upload Baseline
- Dataset Profile
- Target & Features
- Preprocessing Review
- Model & Weighting
- Confirm Configuration shell

## Tests

Scientific/data validation:

- target rules
- cardinality
- low-cardinality warning
- feature-type override
- missing-value consistency
- canonical Parquet stability
- reserved internal column rejection

API:

- baseline upload
- validation states
- configuration
- mutation guards

Frontend:

- setup wizard
- warning states
- binary positive-class requirement
- unsupported-feature handling

## Gate M1

PASS only if a user can:

```text
Create project
→ Upload baseline CSV
→ Validate
→ Review profile
→ Select target
→ Select positive class if binary
→ Configure features/types
→ Review preprocessing
→ Select classifier and weighting
→ Reach training confirmation
```

without any model being trained.

## Milestone commit

```text
feat: add baseline dataset setup and validation workflow
```

---

# 5. Milestone M2 — Baseline Training + Evaluation + Baseline Lock

## Goal

Implement scientifically correct baseline training and freeze a reproducible baseline.

## Training job

Add:

```text
BASELINE_TRAIN
```

Stages:

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

## Training attempt binding

Each training attempt creates a `baseline_snapshot`.

Store:

- dataset ID
- configuration fingerprint
- split metadata
- development/held-out counts
- class support
- methodology version
- code version

## Split

Implement locked:

```text
80% Development
20% Held-out Baseline Reference
Stratified
seed = 42
```

Guardrails:

- effective baseline total = `max(200, 100 × classes)`
- ≥100/class before split
- ≥20/class after actual held-out split

Warn at held-out 20–29/class.

## Cross-validation

Within Development:

```text
5-fold Stratified CV
```

Diagnostics only.

Preprocessing must be fitted independently inside every fold through the sklearn Pipeline.

## Final pipeline

Numeric:

- median imputation
- StandardScaler only for Logistic Regression

Categorical:

- explicit missing category
- OneHotEncoder

Classifier:

- chosen model only

Class weighting:

- Standard / Balanced

## Baseline metrics

Binary and multiclass metrics exactly as locked.

Undefined metrics:

```text
Unavailable + reason
```

## Calibration

Implement:

- reliability bins
- Brier
- Log Loss
- support rules

## Permutation importance

Implement:

```text
held-out reference only
balanced_accuracy
10 repeats
seed 42
raw project columns through full pipeline
```

Negative values remain visible.

## Persist baseline scientific reference

Persist:

- pipeline.joblib
- manifest.json
- artifact SHA-256
- held-out prediction Parquet:
  - row id
  - y_true
  - y_pred
  - probabilities in frozen class order
  - confidence
- split membership artifact
- baseline metrics
- calibration
- permutation importance
- frozen class order
- frozen schema

## Artifact loading

Implement:

- hash check
- artifact version
- Python minor-version policy
- exact scikit-learn compatibility policy

Only worker loads joblib.

## Establish Baseline

Implement:

- snapshot must be `TRAINED`
- fingerprint must match current DRAFT config
- conditional transaction
- snapshot becomes `ESTABLISHED`
- project becomes `BASELINE_READY`
- all baseline-changing routes return 409 afterwards

## UI

Complete:

- training confirmation
- meaningful stage tracker
- baseline Summary
- Performance
- Calibration
- Model Reliance
- Data Reference
- Establish Baseline

Strictly separate:

```text
Development CV
vs
Held-out Baseline Reference
```

## Tests

Leakage:

- held-out mutation cannot alter fitted preprocessing
- current-style data cannot influence pipeline

Metrics:

- known-answer binary
- known-answer multiclass
- undefined cases
- probability class ordering

Calibration:

- bin counts
- support guardrails

Importance:

- raw feature-level importance
- negative values preserved

Baseline lifecycle:

- stale snapshot cannot be established
- config change invalidates trained result
- mutation blocked after establish

## Gate M2

PASS only if a user can create a fully reproducible baseline and the project becomes immutable after establishment.

No monitoring yet.

## Milestone commit

```text
feat: implement reproducible baseline training and locking
```

---

# 6. Milestone M3 — Monitoring Core + Mode A

## Goal

Implement unlabeled monitoring correctly before adding any label-dependent analysis.

This is the key scientific integrity milestone.

## Monitoring run creation

Implement:

- run name
- monitoring date
- notes
- upload
- validation
- baseline snapshot binding

## Validation

Required:

- all model features present
- extras allowed
- numeric coercion rules
- frozen categorical interpretation
- current row minimum 50
- mode detection
- partial-label rejection
- unknown-target-class handling

## Monitoring job

Add:

```text
MONITORING_ANALYZE
```

Mode A stages:

```text
VALIDATING
PREDICTING
DATA_DRIFT
MISSINGNESS
PREDICTION_DRIFT
CONFIDENCE
PERSISTING
COMPLETE
```

## Numeric drift

Use raw non-missing values.

Implement:

- KS
- Wasserstein
- sample n rule
- tied/discrete caution
- range-outside share

## Categorical drift

Use raw non-missing categories.

Implement sample-size-aware pooling:

```text
t = 5 × (n_base + n_current) / min(n_base, n_current)
```

Then:

- reserved internal pooled bucket
- expected-count validation
- chi-square
- `INSUFFICIENT DATA`
- JS distance
- persisted pooling membership

## Missingness

Implement:

- baseline/current %
- pp delta
- zero/zero skip
- chi-square when expected counts valid
- Fisher exact otherwise

## BH/FDR

Per run:

- collect valid feature distribution p-values
- collect valid missingness p-values
- exclude no-test/insufficient
- BH q=.05
- persist family size

## Prediction drift

Held-out baseline vs current:

- predicted class shares
- JS
- categorical test where valid
- baseline/current n

## Confidence

Held-out baseline vs current:

- mean
- median
- histogram data
- KS
- p
- n

## Mode A restrictions

Backend result schema must contain no:

- current performance
- calibration
- confusion matrix
- error analysis
- slice metrics

Report wording audit must prove no forbidden claims.

## Plot data

Worker persists:

- numeric histogram bins
- category shares
- confidence histogram
- prediction shares

API does not calculate statistics.

## UI

Complete:

- New Monitoring Run
- Review mode
- Analysis Progress
- Run Overview
- Data Drift
- Feature Detail
- Predictions
- Confidence
- Mode A Unavailable screens

## Tests

Scientific:

- identical fixture
- shifted fixture
- insufficient sample
- sparse categorical
- unbalanced baseline/current sizes
- missingness Fisher/chi-square
- BH reference vectors

Mode A wording:

assert absence of:

- accuracy degradation
- F1 degradation
- calibration degradation
- model failure
- retrain recommendation

## Gate M3

PASS only if a fully unlabeled current CSV can be analyzed end-to-end with no scientifically invalid performance claim.

## Milestone commit

```text
feat: add unlabeled reliability monitoring and drift analysis
```

---

# 7. Milestone M4 — Mode B Performance + Calibration + Errors

## Goal

Add label-dependent analysis without weakening Mode A.

## Mode B validation

Require:

- complete labels
- frozen class mapping
- no unseen target classes

## Current performance

Implement valid baseline/current metrics.

Always persist:

- baseline value
- current value
- delta
- baseline support
- current support
- availability reason

## Absent-class rules

If baseline class has zero current support:

- valid Accuracy may remain
- class-mix warning
- per-class valid values remain
- invalid macro direct comparisons unavailable
- probability metrics use full frozen class order
- Log Loss / Brier receive class-composition caution

Never compare different macro class sets as equivalent.

## Calibration

Mode B:

- reliability diagram
- Brier
- Log Loss
- 40–99 → 3 bins
- 100–249 → 5
- 250–499 → 8
- 500+ → 10
- ≥20 positive
- ≥20 non-positive
- limited-support warning below 250

Multiclass:

- class-selectable OvR

## Errors

Binary:

- TP/TN/FP/FN
- FP/FN examples

Multiclass:

- confusion matrix
- common confusion pairs

Example rows:

- included model features only
- max 50/view

## UI

Complete:

- Performance
- Calibration
- Classes & Errors
- Mode B Run Overview additions

## Tests

- binary Mode B
- multiclass Mode B
- absent class
- probability order
- Brier/log-loss class mapping
- calibration unavailable cases
- confusion matrices
- error-row privacy/exclusions

## Gate M4

PASS only if Mode B adds valid label-dependent analysis while every M3 Mode A test still passes unchanged.

## Milestone commit

```text
feat: add labeled performance calibration and error analysis
```

---

# 8. Milestone M5 — Feature Diagnostics + Slices + Trends + Reports

## Goal

Complete the diagnostic and historical analysis experience.

## Slice job

Add:

```text
SLICE_ANALYZE
```

Rules:

- Mode B only
- categorical frozen model features only
- one analysis per `(run, feature, methodology version)`
- idempotent repeated request
- n <30 → insufficient
- exploratory wording
- no significance testing
- no fairness claims

## Trends

Implement one selected signal at a time.

Available:

- performance
- probability quality
- confidence
- prediction shares
- feature KS
- feature JS
- missingness

Rules:

- monitoring date order
- no interpolation across unavailable points
- no forecasting
- methodology-version caution

## Reports

At analysis finalization create immutable structured report payload.

Store:

- report template version
- deterministic statements

Sections:

- Project
- Baseline
- Run
- Schema
- Data changes
- Prediction behaviour
- Confidence
- Performance/unavailable
- Calibration/unavailable
- Errors/classes
- Slices
- Limitations

No LLM.

## Methodology page

Static page generated from reviewed documentation.

## UI

Complete:

- Slices
- Trends
- Reliability Report
- Methodology & Glossary

## Tests

- slice support
- slice idempotency
- no fairness terminology
- unlabeled trend gaps
- report immutability
- report Mode A wording
- print-safe content
- methodology-version warning

## Gate M5

PASS only if a project with several Mode A/Mode B runs can be explored historically and exported as a deterministic report without synthetic scoring.

## Milestone commit

```text
feat: add slices trends and deterministic reliability reports
```

---

# 9. Milestone M6 — Full UI/UX Integration + Public Demo Mode

## Goal

Make the entire product conform to the locked UI/UX blueprint and prepare the portfolio-safe public mode.

## UI foundation audit

Ensure:

- light-mode design system
- Baseline vs Current colors
- Inter-style UI typography
- monospace statistics
- status text + icon + color
- responsive behavior
- accessible focus
- keyboard navigation

## Evidence Frame

Standardize:

```text
Measured
Result
Evidence
May conclude
Cannot conclude
```

across analysis screens.

## Mode system

Mode chips:

- Mode A — labels unavailable
- Mode B — labels available

Mode B must not look “healthier”.

## Demo Mode

Fail-closed:

- read-only
- no uploads
- no training
- no delete
- no slice creation unless seeded
- non-GET denied server-side
- frontend visibly disabled
- seeded synthetic/public projects only

Demo seed must be generated through the real pipeline.

## Public demo deployment topology

Demo mode does not need worker if all seed results are precomputed.

## Accessibility

Audit:

- WCAG AA
- keyboard
- focus
- ARIA
- status semantics
- chart/table alternative
- live job updates
- reduced motion
- print without color

## Responsive

Verify:

- desktop
- laptop
- tablet
- mobile review experience

## Portfolio screenshots

Prepare six flagship states:

1. Baseline Results
2. Mode A Run Overview
3. Data Drift / Feature Detail
4. Mode B Performance
5. Calibration
6. Trends

## Gate M6

PASS only if all screens visually and behaviorally match the locked UI/UX blueprint and the public deployment cannot mutate data.

## Milestone commit

```text
feat: complete ModelMedic user experience and demo mode
```

---

# 10. Milestone M7 — Hardening, Scientific QA, CI, Deployment

## Goal

Prove the whole system is scientifically correct, reproducible, secure enough for portfolio use and deployable.

## Full scientific suite

Must include:

- leakage tests
- split reproducibility
- all metrics
- undefined metrics
- class order
- KS
- Wasserstein
- JS
- chi-square
- Fisher
- BH/FDR
- missingness
- calibration
- permutation importance
- Mode A wording
- Mode B edge cases
- slices

## Compute-budget benchmark

Benchmark representative worst cases for:

- Logistic Regression
- Random Forest
- Gradient Boosting

Measure:

- runtime
- peak memory
- encoded dimensionality

Then finalize environment-configured:

- max upload bytes
- max rows
- max columns
- max model features
- max encoded features
- worker timeout
- thread limits

Do not alter scientific methodology.

## Security checks

- no secrets committed
- no user model upload
- object storage private
- safe filenames
- text escaping
- raw rows absent from logs
- demo-mode route audit
- artifact hash/version checks

## CI

GitHub Actions:

### Backend
- Ruff
- type checking
- pytest

### Frontend
- ESLint
- TypeScript
- Vitest
- production build

### Integration
- PostgreSQL
- migrations
- API + worker

### Docker
- build
- Compose smoke

### Security
- secret scanning

## Deployment

Production/demo provider-neutral deployment.

Preferred initial host may be Railway, but code must remain generic.

Use:

- same image for API/worker in Full Mode
- one-shot Alembic migration
- exact locked dependencies
- protected deploy branch/tag
- no deploy after failed CI

## Final E2E scenarios

1. Binary baseline
2. Multiclass baseline
3. Mode A
4. Mode B
5. absent current class
6. sparse categorical drift
7. insufficient drift sample
8. slice analysis
9. report
10. delete
11. demo-mode mutation denial
12. worker crash/retry

## Gate M7

PASS only if:

- complete automated suite passes,
- clean production build,
- Docker smoke passes,
- live deployment works,
- public demo is read-only,
- no critical privacy issue,
- working tree clean.

## Milestone commit

```text
chore: harden test and deploy ModelMedic v1
```

---

# 11. Milestone M8 — Documentation, Portfolio, Resume & Interview Readiness

## Goal

Finish the project as a portfolio asset, not just working code.

## README

Include:

- one-line problem
- project screenshot
- why ModelMedic exists
- Mode A vs Mode B
- architecture diagram
- workflow
- scientific methodology
- screenshots
- limitations
- local setup
- Docker setup
- demo link
- testing
- security/demo note
- future scope

## Documentation

Finalize:

```text
docs/methodology.md
docs/architecture.md
docs/limitations.md
docs/demo-guide.md
```

## Portfolio

Prepare:

- 60-second explanation
- 2-minute walkthrough
- 5-minute technical demo

## Resume

Create 2–3 concise bullets emphasizing:

- ML reliability/statistics
- full-stack architecture
- reproducibility/testing

No inflated claims.

## Interview Study Guide

Must cover:

- why drift ≠ degradation
- Mode A vs B
- why held-out reference exists
- why full baseline is used for raw drift
- why BH correction
- KS limitations
- categorical pooling
- calibration
- Brier/log loss
- permutation importance
- class order
- why no health score
- why no retraining
- PostgreSQL worker queue
- Parquet
- joblib safety
- artifact hashes/versioning
- demo mode

## Final Repository Audit

Check:

- commit identity uses intended GitHub noreply identity
- no private email
- no credentials
- no private datasets
- no generated junk
- README accurate
- release tag

Suggested tag:

```text
v1.0.0
```

## Gate M8

PASS only when the repository is understandable and defensible without reading the source code first.

## Milestone commit

```text
docs: finalize ModelMedic portfolio and interview materials
```

---

# 12. Gate Summary

| Milestone | Gate |
|---|---|
| M0 | Architecture foundation works |
| M1 | Baseline setup complete |
| M2 | Baseline trained, evaluated and frozen |
| M3 | Mode A scientifically correct |
| M4 | Mode B scientifically correct |
| M5 | Diagnostics/history/report complete |
| M6 | Final UX + safe demo mode complete |
| M7 | Scientific QA + CI + deployment pass |
| M8 | Portfolio/interview ready |

---

# 13. Git Discipline

Before every milestone commit:

```text
git status
tests
lint
type check
Docker checks where applicable
privacy/secret scan
```

Then:

```text
git add ...
git commit -m "<milestone message>"
git push
```

Do not create meaningless commits after every tiny edit.

The milestone commit should represent a coherent verified unit of work.

---

# 14. Codex Execution Rule

Codex must work on **one milestone only**.

At the end of every milestone it must return:

```text
MILESTONE:
STATUS: PASS / PASS WITH ISSUES / FAIL

IMPLEMENTED:
- ...

TESTS:
- ...

MANUAL CHECKS:
- ...

KNOWN ISSUES:
- ...

LOCKED DECISIONS PRESERVED:
- ...

GIT:
- commit hash
- commit message
- branch
- working tree status

NEXT:
- exact next milestone
```

If the milestone gate fails:

> Stop. Do not begin the next milestone.

---

# 15. Final Build Order

```text
M0 Foundation
 ↓
M1 Dataset Setup
 ↓
M2 Baseline
 ↓
M3 Mode A
 ↓
M4 Mode B
 ↓
M5 Diagnostics / History / Report
 ↓
M6 Final UX / Demo
 ↓
M7 QA / CI / Deployment
 ↓
M8 Portfolio / Interview
```

---

# Status

## STEP 8 — MILESTONE IMPLEMENTATION PLAN: READY

Next planned step:

> **STEP 9 — Master Codex Build Instruction**

The Master Codex instruction should attach/reference:

1. Final PRD v1.0.1
2. Final Technical Architecture Blueprint v1.0
3. Final UI/UX + Dashboard Blueprint v1.0
4. This Milestone Implementation Plan

Codex should then execute M0 only, stop at the M0 gate, report results and wait for the next milestone instruction.
