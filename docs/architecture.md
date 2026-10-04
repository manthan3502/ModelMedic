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
