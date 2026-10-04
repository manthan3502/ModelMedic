# M2 — Reproducible Baseline Training and Locking

Status: **PASS**. Final complete gate executed successfully on 2026-10-04,
including the post-commit artifact-cleanup failure regression.

## Implementation and scientific decisions

The existing PostgreSQL worker executes BASELINE_TRAIN with the locked nine
stages. Each execution owns a snapshot and server-generated write-once artifact
prefix. Claim, heartbeat, retry and final publication retain M0 fencing semantics.
The API never trains or deserializes a submitted model.

The deterministic 80/20 split, five Development-only folds, fold-local complete
pipelines, selected classifier and Standard/Balanced weighting follow the locked
contract. The final Development fit produces official held-out metrics, support,
calibration and raw-feature permutation importance. Full implementation choices
and pinned versions are in [methodology.md](methodology.md).

The UI now runs confirmation → stage tracker → results → establishment. Summary,
Performance, Calibration, Model reliance and Data reference preserve the visible
distinction between held-out official evaluation and diagnostic Development CV.
There is no monitoring, current-data upload, drift, AutoML, tuning, model ranking,
ECE, recalibration, deployment or recommendation functionality.

## Executed acceptance checks

The final executable command is `./scripts/m2-gate.ps1`. It includes the full
M0 and M1 gates; no Docker or PostgreSQL check is substituted or skipped.

| Check | Result |
|---|---|
| Ruff, format and strict mypy | PASS |
| Full backend/scientific/PostgreSQL tests | PASS — 94 tests, no skips |
| Frontend ESLint, TypeScript and production build | PASS |
| Frontend tests | PASS — 12 tests |
| npm audit | PASS — zero vulnerabilities |
| Compose config, image builds, service startup, explicit migration | PASS |
| M0 live/ready/worker/queue and frontend hostname/proxy smoke | PASS |
| M1 streamed CSV-to-confirmation smoke without automatic training | PASS |
| M2 real-stack target/model/weighting combinations | PASS — all 12 |
| Privacy/secret scanner and manual source review | PASS |
| Locked specifications | PASS — byte-identical to 8e2029a and approved M1 |
| Scope review | PASS — no M3 functionality |

Additional executed checks verified the 24/class low-support warning and
inverse-frequency Balanced weights on a 300/100 imbalanced label vector.

## Every M2 gate criterion

| Criterion | Evidence / result |
|---|---|
| BASELINE_TRAIN and all required stages | PASS — worker execution and exact stage assertions |
| Concrete snapshot per execution, ownership-fenced atomic publication | PASS — PostgreSQL lifecycle/fencing tests |
| 80/20 stratification, seed 42, no membership overlap | PASS — deterministic split tests and persisted IDs |
| Pre-split and authoritative actual held-out guards | PASS — failure prevents trained artifacts/establishment |
| Held-out 20–29 support warning | PASS — deterministic result generation |
| Five-fold Development-only CV | PASS — exact fold membership checks |
| No preprocessing/classifier leakage | PASS — held-out mutation, future-style inference and fit-boundary tests |
| Numeric median; LR-only scaling; categorical missing/OHE | PASS — all three classifiers and both weights |
| Only chosen model; no optimization or resampling | PASS — source review and enum validation |
| Binary/multiclass metrics and undefined reasons | PASS — known answers against sklearn |
| Frozen class/probability order and explicit positive index | PASS — reversed-order and index-zero tests |
| Calibration quantile policy, support and bin counts | PASS — every threshold, ties and multiclass curves |
| Full-pipeline raw held-out permutation importance | PASS — scorer/repeat/seed/input-boundary assertions |
| Negative importance preserved | PASS — controlled negative result test and UI test |
| Pipeline, manifest/hash/version and environment persistence | PASS — real artifacts and guarded reload |
| Held-out predictions/probabilities/confidence and split artifacts | PASS — reference reload and membership assertions |
| Scientific outputs persisted without historical recomputation | PASS — worker publication and read-only result endpoints |
| Hash/artifact/Python/sklearn rejection before deserialization | PASS — loader spy proves no load on failure |
| Snapshot fingerprint rejects stale/config-mismatched establishment | PASS — PostgreSQL tests |
| Draft dependency change requires discard confirmation | PASS — API and frontend tests |
| Establish atomically freezes snapshot and project | PASS — all 12 real-stack cases |
| Every existing baseline mutation blocked after establishment | PASS — upload, configuration fields, train, establish, delete |
| Summary/Performance/Calibration/Reliance/Reference UI | PASS — browser and frontend tests |
| Calm establishment and post-establishment read-only behavior | PASS — browser and API tests |
| Full M0/M1 regressions | PASS — existing guarantees retained |

## Docker, database and end-to-end evidence

Verification stack: `modelmedic-m2-verified`.

- Frontend: loopback 15178; API: loopback 18005.
- API and PostgreSQL healthy; worker heartbeat and real jobs verified.
- PostgreSQL remains private on its Compose network.
- Revision 0003_m2 is additive above preserved 0002_m1 and 0001_m0.
- Tests create a fresh disposable PostgreSQL database, check schema agreement,
  preserve an M0 project across migration round-trip, and delete only that database.
- All 12 binary/multiclass × LR/RF/GB × Standard/Balanced workflows establish
  successfully. Their generated projects are removed with test-only cleanup.

Browser verification used a generated 400-row CSV: 320 Development rows, 80
held-out rows and 40 held-out observations per class. It explicitly selected the
positive class at probability index zero, trained, visited all five result
sections, established the baseline and verified an editing URL displayed a locked
view. At 320px the document width stayed within the viewport; result tables and
manifest hashes remain contained. Temporary viewport override was reset.

## Artifacts and reproducibility

Each successful snapshot retains pipeline.joblib, manifest.json, results.json,
heldout.parquet and split.parquet. Reload predictions exactly match the original
pipeline probabilities in the verified environment. The manifest records Git SHA,
dirty/clean source state, source digest, canonical hash/version, frozen schema,
class order, selected settings, runtime versions and model SHA-256.

Draft verification artifacts identify their parent Git SHA and dirty source state.
A clean build after the milestone commit stamps new attempts with the final SHA.
Historical manifests are never rewritten to disguise their build provenance.

## Privacy, locked specifications and known limitations

Only synthetic test data was used. No CSV, Parquet, joblib, .env, generated build,
private email, credential or token is staged. Storage is private and server-keyed;
errors and logs do not include uploaded rows. The four locked files are compared
as raw bytes against Git blobs, avoiding checkout newline-filter ambiguity.

No unresolved functional gate failure is accepted. The existing Starlette
TestClient/httpx deprecation remains a warning. Deployment throughput and
worst-case capacity are not claimed by this local milestone. If external old-object
cleanup fails after a draft discard, its unreferenced private prefix is logged for
cleanup and removed with project deletion; it cannot be established or loaded.

## Git and next milestone

This verified milestone is committed with the single authorized subject:
`feat: implement reproducible baseline training and locking`.

Approved M1 parent: `8627817f6998514ea33730b87dac0f2150b5a70c`.
No starting/M0/M1 commit is amended or rewritten. Final commit SHA, push result,
remote equality and clean working-tree verification are reported in the completion
message after the final gate and commit.

Next: M3 — Monitoring Core + Mode A. **STOP BEFORE M3.**
