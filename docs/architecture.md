# M0 foundation notes

This is implementation documentation, not a replacement for the locked
[architecture](specs/ModelMedic_Technical_Architecture_Blueprint_v1.0_LOCKED.md).

- One backend codebase, one shared API/worker image, two processes.
- Synchronous SQLAlchemy 2.x and PostgreSQL only.
- Alembic revision `0001_m0` creates six minimal domain tables plus worker status.
  Later fields/results are intentionally deferred to their owning milestones.
- Readiness requires a reachable database and exactly the supported schema head.
- Job claims use `FOR UPDATE SKIP LOCKED`, increment the attempt and assign a
  fresh UUID ownership token. The transaction commits before execution begins.
- Active-target uniqueness is enforced by a PostgreSQL partial unique index.
  Internal jobs always have a UUID target, avoiding nullable uniqueness gaps.
- Worker heartbeats are independent of jobs. While computing, a separate thread
  uses short independent transactions to renew the job lease and worker heartbeat.
- Heartbeat and finalization require an unexpired lease, matching attempt/token
  and RUNNING state. Expired/replaced attempts cannot publish a terminal state.
- Recovery requeues only when attempts remain (default two total); exhaustion
  fails with `WORKER_LOST`. Computation failures terminate without automatic retry.
- M0 dummy jobs have internal targets and no result rows. Future scientific
  finalizers must add target lifecycle checks and result writes in the same fenced
  transaction; M0 does not pretend those later workflows already exist.
- API response contracts exclude job parameters and ownership tokens. Errors use
  `code`, `message`, `details`, `request_id`; logs contain reviewed events and IDs.
- ArtifactStore is a structural protocol. Local objects are write-once and
  atomically published; prefix deletion validates containment before removal.
- Inter and JetBrains Mono are bundled locally. The shell uses the locked light
  theme, readable semantic structure, focus styles, route focus and mobile navigation.
- M0 has no scientific library, upload, training or analytical result implementation.

Dependency versions are captured in `uv.lock` and `frontend/package-lock.json`.
The Compose frontend is for development; production same-origin hosting is deferred.

## M1 extension

Revision `0002_m1` extends draft projects with normal target/positive-class/model/
weighting/activity columns, nested setup selections, recoverable deletion state,
and datasets with validation status, profile/report and hash/version metadata.
M0 rows survive upgrade. No result/metric table or trained baseline is produced.

Upload streaming holds no database transaction. Acceptance rechecks draft state
and active jobs while locking the project, then atomically publishes server-keyed
original CSV and queues validation metadata. Computation runs outside transactions.
Canonical objects use attempt-specific write-once keys. Dataset results and job
completion share a fenced transaction that also rechecks project/dataset lifecycle.
Losing ownership removes that attempt's canonical publication.

The profile and schema review preserve raw category spellings, only normalize
empty/whitespace-only cells to null, and use stable feature IDs rather than headers
in API paths. The canonical format deliberately stores lossless nullable strings
plus uint64 row IDs; feature semantics and permitted conversions are separate
from storage dtypes. See the README import contract for exact parser/serialization
rules. No fitting or train/test split occurs during setup.


## M2 and M3 extensions

M2 (`0003_m2`) persists concrete training snapshots, guarded pipeline/manifest,
all-row canonical drift reference, held-out reference and split membership.
Establishment freezes the project/snapshot configuration fingerprint. The API
never loads joblib; worker-only trusted artifact loading verifies hash and versions.

M3 (`0004_m3`) adds monitoring metadata, exact snapshot binding, immutable result
provenance and per-feature result rows. Scalar queried fields/status/p-values are
normal columns; nested chart/pooling/evidence values are JSONB. History is indexed
by project, monitoring date, creation timestamp and ID. Database triggers reject
binding changes and published result mutation. No M4 result tables/calculations
are introduced.

Current uploads count bytes during streaming in a private temporary file, then
lock the mutable run to publish a server-generated original key and enqueue
DATASET_VALIDATE in one transaction. The shared strict CSV parser is reused;
current semantic types come only from the established snapshot. A successful
compatibility report exposes mode before the explicit analyze action.

MONITORING_ANALYZE reads hash-verified immutable canonical and held-out artifacts,
loads the frozen pipeline in the worker, predicts only on current rows and computes
raw observed-value drift separately from missingness. Histogram/share/test output
is prepared once by the worker. Existing lease/owner/attempt fences atomically
publish feature rows, nested results, object hash, provenance and ANALYZED state.
API routes only serialize stored outputs. Failure/stale ownership exposes no
partial final result. Analyzed run uploads/reanalysis are rejected.

Deletion checks active jobs, records deletion_pending before removing the private
run prefix and cascades run/result/job/import metadata afterward. External cleanup
failure remains recoverable by retry. Existing M2 draft-artifact cleanup behavior
is preserved. Full report export remains future work.

## M4 labeled monitoring extension

Additive revision `0005_m4` adds `run_metrics`, `run_calibration_results` and
`run_error_results`. Metric values, signed deltas, support, scope, class, status
and reasons are normal columns. Nested calibration bins, confusion counts/rates,
common pairs and bounded canonical row references are JSONB. Class composition is
saved in the immutable run result. No full example rows are stored in PostgreSQL.

The existing MONITORING_ANALYZE job accepts validated Mode A or Mode B. Mode B
extends the existing stages with PERFORMANCE and CALIBRATION; both modes retain
the same ownership/lease/attempt fence. All feature and labeled result rows are
inserted while the run is READY and flushed before sealing it ANALYZED in the
same finalization transaction. New result-table triggers reject updates and
inserts against already analyzed runs. Results remain inaccessible before commit.

Mode B performs frozen current inference once, reuses unchanged M3 drift and
behavior analysis, and reads historical performance/calibration from the hashed
M2 results artifact. Historical values must match the frozen snapshot metadata.
No baseline value is reevaluated. API endpoints serialize saved evidence and
never load a model or compute scientific statistics.

The bounded error-example endpoint validates a saved view and canonical hash/
schema version, projects only included model features plus internal row ID, then
retrieves the saved row references. Arbitrary views/paths are rejected. Empty
views use typed Arrow indices and return an empty table. React escapes cells.
Mode A keeps the original unavailable contracts. Slices, trends and report
generation are not implemented by M4.
