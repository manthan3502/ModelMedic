# M7 verification record

**MILESTONE:** M7 — Hardening, Scientific QA, CI, Deployment.
**STATUS:** Pre-commit engineering, live deployment and manual print gates PASS.
Git finalization and hosted CI on the exact milestone commit are checked after push.
**RECORD SCOPE:** Evidence frozen before the single M7 commit on 2026-10-14; the
completion report records its exact SHA, push, CI conclusion and clean tree.
**NEXT:** M8 — Documentation, Portfolio, Resume & Interview Readiness. **STOP before M8.**

The locked milestone plan §10 requires “live deployment works.” The public
[Railway Demo](https://modelmedic-production.up.railway.app) now satisfies that
requirement. Operator evidence is identified separately from checks independently
executed during finalization. No locked specification or methodology was changed.

## Implementation and scientific QA

Direct audit of baseline, Mode A, Mode B, slices, trends, reports and trusted
artifact loading is mapped in [the scientific audit](m7-scientific-audit.md).
No scientific formula, threshold, method/version, model parameter, reference
population, split, feature semantics or dependency pin for scientific libraries
changed. Added SciPy known-answer fixtures use rtol 1e-12 and atol 1e-15 where
appropriate; existing sklearn reference and exact accounting tests remain passing.

Hardening adds a private conditional-write S3 store, Demo read-only storage guard,
built React same-origin serving, trusted hosts/security headers/request IDs, PORT
entrypoint, non-root production image, supervised worker computation with an
1800-second default deadline, and pinned four-job GitHub Actions verification.
Production operator seed/probe CLI modules ship without HTTP endpoints or test
runtime dependencies. TestClient uses locked httpx2, eliminating its carried
Starlette/httpx warning without changing the scientific/runtime framework pins.

UI fixes are limited to the Baseline/first-date Trends collision, a live-region
explanation when feature filters match no rows, and wrapping long unbroken labels
inside the workspace. There is no visual-system redesign.

## Tests and checks

Final fresh Compose project `modelmedic-m7-compose-portable-20261014` passed the entire
M0–M7 stack gate from unused volumes: 194 backend tests in 88.12 s (131
unit/scientific + 63 PostgreSQL integration), an additional mandatory 63-test
PostgreSQL run in 86.41 s, frontend lint/TypeScript/47 tests/build/audit, all twelve
baseline combinations, Full Mode monitoring/slices/reports, empty migrations,
clean B–A–B seed, Demo enumeration, restart fingerprints and production-image
smoke. Alembic check found no new upgrade operations. Both production smoke
passes covered 24 same-origin deep links/private paths/mutation boundaries.
The new image-only check proved default `/artifacts` scratch writes work as uid
10001 without provider secrets or network access.

Separately executed the real clean `npm ci` plus lint, TypeScript, all 47 tests,
production build and audit on Node 24.14.1: zero vulnerabilities. Backend Ruff,
format check (93 files), mypy (61 sources), workflow structural guard and official
actionlint 1.7.12 passed. Native Windows scientific/unit replay passed 131 tests
with 63 integration tests correctly deselected. It emitted one local pytest cache
permission warning; the Docker full suite was clean, and the old TestClient/httpx
warning remains eliminated. Native replay used the same one-thread numeric-library
settings as CI/Docker after a stalled duplicate invocation was stopped.

CI commands have run locally against locked installs and real PostgreSQL/Linux
containers. Hosted CI is intentionally checked only after the final milestone
commit is pushed; its exact run/conclusion belongs to the completion report.
No hosted green check is claimed in this pre-commit record. Integration CI requires
TEST_DATABASE_URL and cannot silently skip PostgreSQL. Actions and base images use
immutable revisions. Automatic deployment must remain gated on successful CI.

The first hosted backend run exposed an exact floating-point assertion: SciPy on
the Ubuntu runner returned Wasserstein distance 200.00000000000003 for an expected
200. The test now uses explicit absolute tolerance 1e-12 with zero relative
tolerance. No scientific calculation, threshold or returned result was changed.
Only the unapproved M7 commit is amended to include this test portability fix;
the approved M6 parent remains untouched and there is still one final M7 commit.

Hosted PostgreSQL CI also exposed missing source provenance in the standalone
test job. Training correctly rejected the default unknown SHA. CI now supplies
its actual github.sha and clean-checkout dirty=false; the application guard is
unchanged. The workflow verifier requires those settings, and PostgreSQL health
checks use the configured test role/database. These CI configuration fixes are
included by amending only the same unapproved M7 commit.

The hosted system runner's Compose version rejected `--wait` for the worker's
explicitly disabled HTTP healthcheck. Full Mode orchestration now waits on the
database/web healthchecks separately and verifies the worker with actual heartbeat
and executed dummy-job checks, including after restart. No readiness check is
replaced by a no-op, and no training/analysis/Docker gate is skipped.

Independently executed the documented direct-file public HTTPS smoke on
2026-10-14: UI/deep links, B–A–B gap, all 180 prohibited method/route combinations
and persisted fingerprints PASS. An initial read timeout was transient; the
complete smoke subsequently passed without changing its timeout or checks. A
separate direct-file import defect was fixed by resolving the trusted repository
root, without requiring PYTHONPATH or changing the application. Public artifact
and unreviewed reads returned 403; a non-seeded project returned the specified
404 hiding response. Mode A metrics/calibration both returned UNAVAILABLE with
the ground-truth-label explanation. No current degradation verdict is inferred.

The operator confirmed an additional full public smoke before and after scaling
both private seed services to zero. The production private S3 read/write/hash,
conditional overwrite rejection and scoped cleanup probe passed during deployment;
this is operator-confirmed evidence, not a claim of agent access to bucket secrets.

Evidence logs/measurements are ignored under .cache; no data/model/screenshot is
a commit candidate. Commands and reproducible operator procedures are documented
in [M7 operations](m7-operations.md).

## Edge-case QA

Executed suites cover minimum 2/3/10-class baseline/support guards, extreme
imbalance, constant and near-all-missing numeric inputs, allowed all-missing
categorical inputs, unseen categories, categorical cardinality, numeric-looking
literal strings, whitespace-distinct categories, absent current classes, current
50-row minimum, 29/30 drift and slice support, 19/20 calibration event support,
duplicate metadata ordering, immutable reloads, failures/retries and stale recovery.
Parser checks include empty/header-only, malformed/encoding/duplicate/reserved
columns, pathological cell lengths, streamed limit without Content-Length,
dangerous filenames, literal formula/script-like cell values and no destructive
cleaning. React escaping and no dangerous HTML paths were reviewed.

## Performance / resource validation

Six synthetic training benchmarks were completed earlier in M7 (2026-10-05)
and retained as measured resource evidence: scientific code, pins and limits remain
unchanged. They ran in Linux containers with 2 CPUs, a 6 GiB
memory ceiling and numeric library thread counts 1, using Balanced weighting.
Training includes five CV fits, final development fit, held-out metrics,
calibration and raw-feature permutation importance. Monitoring measures Mode A.
Peak RSS is approximate **single-process** Linux ru_maxrss, not total stack usage.
Artifact sizes below are bytes: canonical / model / held-out reference / membership.

| Case / classifier | Rows | Actual encoded | Validation s | Training s | Monitoring s | Peak RSS MiB | Artifact bytes |
|---|---:|---:|---:|---:|---:|---:|---|
| encoded / gradient_boosting | 5,000 | 1,970 | 0.63 | 125.92 | 0.75 | 450.9 | 675,723 / 51,859 / 290,924 / 30,705 |
| encoded / logistic_regression | 5,000 | 1,970 | 0.55 | 37.38 | 1.15 | 447.3 | 675,723 / 19,257 / 290,942 / 30,705 |
| encoded / random_forest | 5,000 | 1,970 | 0.67 | 68.95 | 1.24 | 476.9 | 675,723 / 3,671,763 / 266,158 / 30,705 |
| rows / gradient_boosting | 50,000 | 50 | 7.47 | 592.99 | 4.00 | 602.3 | 8,332,930 / 52,989 / 3,566,433 / 309,507 |
| rows / logistic_regression | 50,000 | 50 | 8.28 | 114.39 | 3.59 | 570.3 | 8,332,930 / 3,839 / 3,566,765 / 309,507 |
| rows / random_forest | 50,000 | 50 | 7.37 | 518.43 | 5.47 | 724.0 | 8,332,930 / 21,263,411 / 3,300,437 / 309,507 |

The encoded fixture estimates 1,990 columns and produces 1,970 because missing
categories are estimated but not observed in that fixture. A separate joint-bound
fixture actually produced **2,000 encoded columns at 50,000 rows/50 features**:
validation 8.18 s; development-only preprocessing fit and held-out transform 4.18 s;
peak RSS approximately 1,768.8 MiB; development dense matrix 640,000,000 bytes,
held-out 160,000,000 bytes; canonical 6,405,485 bytes; CSV 14,279,209 bytes.
**Classifier training at that joint maximum was not run.** This is a bounded
allocation check, not a throughput/enterprise-scale claim.

Exact guards were exercised for 25 MiB/one-byte-over parsing, 50,000/50,001 rows,
100/101 columns, 50/51 features and the 2,000 encoded estimate. Category boundary
100 remains unchanged. No default limit was increased. The 1800-second supervised
execution limit and one-thread settings bound computation; capacity still depends
on provider allocation. Do not promise simultaneous maxima on small hosts.

## Database / migrations / worker / concurrency

No M7 migration was needed. Empty disposable PostgreSQL migrated 0001_m0 through
0006_m5. Alembic check/schema-ORM agreement, foreign keys, cascades, uniqueness,
active-job constraints, immutable publications and baseline lifecycle passed.
Real PostgreSQL tests cover concurrent SKIP LOCKED claims, duplicate prevention,
lease renewal/heartbeat/stale recovery/max attempts, owner fencing, old-owner
rejection and no partial publication. New real-process tests verify deterministic
JOB_TIMEOUT failure and shutdown/restart with a new lease token. Production
startup does not migrate implicitly; the operator runs Alembic once.

## UI hardening / accessibility / print QA

Browser audit on the production build checked all six portfolio views (Data and
Feature Detail separately) at 320, 768, 1024 and 1280 pixels: 28 measurements, no
page-level horizontal overflow. Analytical tables/charts scroll within their own
containers. Computed visible HTML text contrast was at least 5.24:1; disabled
controls and SVG graphics were excluded from that measurement and reviewed
separately. One h1, semantic table headers, labels, evidence/claim boundaries,
status text/icons, unavailable explanations and textual/table chart alternatives
were checked. Keyboard Enter navigation restored MAIN focus; visible focus and
mobile navigation were exercised. Reduced-motion rules were inspected.

A real-pipeline long-name fixture exposed class-heading ink extending a 320 px
page to 993 px. Wrapping fixed it; Performance, Calibration and categorical
Feature Detail passed twelve checks across the same four widths. Long category,
class and feature names remain complete. The final gate-04 production build repeated all 28 standard-screen width/contrast
checks successfully; its computed text minimum remained 5.24:1. Saved synthetic
Mode B slices were also verified in the final print preview. The empty filter now announces a helpful
no-match explanation through role=status. Calibration points expose mean
probability, observed frequency and n to keyboard/screen-reader users.

Mode A and Mode B onscreen print previews passed: black/white readable values,
hidden navigation/controls, static table headers, complete table alternatives,
no page-level clipping and Mode A unavailable wording. The operator subsequently completed all four native previews: Mode A/A4,
Mode A/Letter, Mode B/A4 and Mode B/Letter, portrait, 100%, normal margins,
background graphics off. No clipping, overlap, broken sections, bad pagination
or unexpected blank pages was observed. This is explicit operator-confirmed
manual evidence; the agent did not automate the OS dialog. Exact repeatable
instructions remain in M7 operations. No server PDF generator was added.

## Demo Mode security / seed

Server guards and route enumeration passed in real Full/Demo stacks. All 180
POST/PUT/PATCH/DELETE/OPTIONS/HEAD method-route pairs were denied before and after
restart, including actual frontend proxy and production one-origin routes.
Seeded-ID scope, later Full Mode additions to seeded projects, inaccessible/missing
or changed registry, non-local mode configuration, and storage writes fail closed.
Full Mode remains functional. No worker runs or is required in final read-only Demo.

Clean synthetic seeding uses real upload/validation/training/establishment/analysis
jobs; B–A–B outputs include saved slices/trends/reports. Source hashes and persisted
summary/report fingerprints verified after restart. The relocated generator's
source and digest logic preserve M6 behavior; nothing hand-authors scientific
outputs. The seed/operator commands are documented and available in production.

## Security / privacy / artifact compatibility

Internal joblib deserialization remains worker-only, after SHA-256, artifact
version, Python minor, exact sklearn and manifest/class ordering checks. Corrupt,
missing and incompatible artifacts are rejected before unpickling. No model
upload/download endpoint or public artifact URL was added. Storage uses generated
keys, traversal rejection, conditional write-once puts and scoped cleanup; Demo
blocks every storage mutation. Production requires private S3 configuration.

Privacy scan covers current candidates, ignored-env secret matching without
printing values, all eight historical commits/unique blobs and author/committer
noreply identities. Raw bytes of all four locked specifications are compared to
8e2029a, beyond Git's newline normalization. Complete diff review checks source,
dependencies, operations, workflow and docs; runtime/synthetic/cache files remain
ignored. No history rewrite, secret, private dataset or prohibited product scope
was found. The final current/history privacy and raw-byte integrity scan passed after this
report was finalized; it does not replace human review of the candidate diff.

## Production config / containers / deployment

Same-origin built React/API production runtime, trusted controlled hosts, security
headers, no access/body logging, request IDs, env-only secrets, health/readiness,
explicit mode and PORT start command are implemented. Runtime inspection confirmed
uid 10001, built assets, and absence of .env, tests, scripts, cache and pytest.
A separate actual production container served readiness on supplied PORT=8012;
the image health check also reads PORT. This probe used a bounded startup wait.
The helper container was stopped and removed.
API and worker share the backend production image. Test tooling has a separate
build stage; the default build is production. No Kubernetes or extra queue system.

**DEPLOYMENT: PASS.** Public URL:
[ModelMedic Production](https://modelmedic-production.up.railway.app).
Railway ModelMedic / Production runs the public `modelmedic` Demo service,
managed PostgreSQL and private S3-compatible bucket. The one-shot `seed-operator`
completed. Private `seed-api` and `seed-worker` are scaled to zero; public runtime
is DEMO_MODE/read-only and reports NOT_REQUIRED for the worker.

Production synthetic project `da55df0a-ca7f-44e0-a581-697f55d9f382` was seeded
through real jobs, with B–A–B results, saved slices/trends/reports and verified
source/persisted hashes. The actual provider probe passed. These private topology
and probe facts were confirmed by the operator; agent verification independently
checks the external app, health, no-worker semantics, scope rejection and mutation
denial. No production administration credentials were printed or committed.

Railway listens on provider PORT=8080 through `backend.app.web`. Every deployment
container uses `MM_ARTIFACT_ROOT=/artifacts` for writable private scratch even
with S3. The production Dockerfile now sets that default explicitly, and the gate
verifies non-root writes. The exact public host is trusted without a wildcard.
Deployed/seeded provenance still identifies the approved M6 parent with dirty=true,
as expected for the uncommitted M7 candidate used for the live gate. The final
commit does not rewrite immutable seed results or imply the deployed image has
already been rebuilt from its new SHA. Source of truth remains this Windows repo.

Temporary baseline_upload_* logging is absent. `backend/app/api/projects.py`
remains identical to M6; main retains only the reviewed `request_failed` event,
without exception serialization or exc_info. No WSL deployment copy was imported.

**POST-DEPLOYMENT VERIFICATION: PASS.** Independent full external HTTPS smoke
and operator before/after-zero-worker smoke succeeded. No public Full Mode was
exposed. The deployment procedure remains in [M7 operations](m7-operations.md).
**DOCUMENTATION:** Scientific audit, reproducible verification/operations guide,
Railway configuration and this report only; no M8 portfolio/README/resume polish.

## Locked specifications / known issues / Git

All four specs remain byte-for-byte identical to the original locked commit.
No method, architecture, visual system, milestone ordering or history was silently
changed. No retraining/serving, alerts/streaming, Kafka/Kubernetes, authentication
platform, dark mode, scoring, LLM/assistant, AutoML, model-family or task expansion.

Carried limitation: failed cleanup can leave an inaccessible private prefix until
retry/discard/project deletion. Direct review found a durable fix needs additional
ownership bookkeeping; no risky architectural cleanup redesign was made. Exact
safe operational response is documented. Starlette/httpx warning is resolved.
Clean npm install still emits development dependency deprecation/allowScripts
notices (eslint/whatwg-encoding/esbuild); audit reports zero vulnerabilities.
Resource findings are synthetic bounds, not guarantees. Native paper preview
and actual private bucket compatibility were completed by the operator. The
initial Windows pytest replay emitted a cache permission warning; this environment
warning does not change the clean Docker acceptance results.

At this pre-commit checkpoint main/HEAD and live origin/main matched approved
M6 `e1cf858bb30de58aad67ff637a1d4bf69561a0b1`. Noreply author/committer identity,
original spec bytes, no scientific/migration changes and full candidate privacy
were checked. Exactly one final M7 commit with the requested message is prepared
on that parent. Push, exact SHA, hosted CI and clean working tree are verified
subsequently in the completion report; this source record cannot include its own
commit hash. No approved milestone is amended or rewritten, and no extra cleanup
commit is planned.

## Locked M7 acceptance gate

| Locked gate item | Status | Evidence |
|---|---|---|
| Complete automated suite | PASS | Fresh 2026-10-14 gate and CI commands |
| Clean production build | PASS | Built/tested production image and final browser checks |
| Docker smoke | PASS | Full/Demo/production/restart flows |
| Live deployment works | PASS | Actual Railway HTTPS smoke and provider/operator evidence |
| Public demo is read-only | PASS | Actual public runtime, 180 denials, scope hiding and no-worker check |
| No critical privacy issue | PASS | Final candidate/history scan and manual review |
| Working tree clean | VERIFY AFTER COMMIT | Final single commit/push/clean-tree check in completion report |

## Every requested criterion

| # | Criterion | Status | Evidence / remaining action |
|---:|---|---|---|
| 1 | Direct scientific audit | PASS | Spec-to-code review and audit map; no method change |
| 2 | Scientific known answers | PASS | SciPy/sklearn references, explicit tolerances/accounting |
| 3 | Edge-case matrix | PASS | Unit/scientific and real PostgreSQL fixtures |
| 4 | Resource / scale | PASS | Six classifier benchmarks, joint dense allocation, exact guards; stated limits |
| 5 | Upload/parser safety | PASS | Streaming/parser/path/literal-value cases and UI escaping |
| 6 | Artifact safety/compatibility | PASS | Corrupt/missing/hash/version/manifest/classes before load |
| 7 | DB/migrations | PASS | Empty 0001–0006, schema check, constraints; no new migration |
| 8 | Jobs/worker | PASS | Real PostgreSQL fencing/concurrency and spawned timeout/restart |
| 9 | Cleanup issue | PASS | Inspected; permitted carried limitation documented |
| 10 | Starlette/httpx warning | PASS | Compatible locked httpx2; complete suite without prior warning |
| 11 | Six-screen visual hardening | PASS | Trends collision and long heading fixes; responsive evidence |
| 12 | Accessibility | PASS | Contrast, keyboard/focus, labels/status/alternatives/reduced motion |
| 13 | Print | PASS | CSS previews plus all four operator-confirmed native A4/Letter checks |
| 14 | Demo security | PASS | Fail-closed routes/seed scope/storage; all 180 prohibited pairs |
| 15 | Clean/reproducible seed | PASS | Real pipeline, restart hashes, slices/trends/reports; no worker |
| 16 | Privacy/secrets/history | PASS | Current candidates/eight historical commits/original raw spec bytes |
| 17 | CI implementation | PASS | Four pinned jobs, guards, real failure propagation |
| 18 | CI local reproducibility | PASS | Actual local commands/actionlint; hosted execution not claimed |
| 19 | Production configuration | PASS | Explicit env/hosts/mode/private store/one-origin/health/commands |
| 20 | Production containers | PASS | Non-root/default production/runtime contents/actual smoke |
| 21 | Railway deployment | PASS | Live public Demo, private DB/bucket, completed actual provider probe |
| 22 | External post-deployment | PASS | Independent full HTTPS smoke; operator before/after-zero-worker verification |
| 23 | Operator documentation | PASS | Non-locked operation/audit/verification docs |
| 24 | Full M0–M6 regressions | PASS | All automated suites and Full/Demo stack flows |
| 25 | Final repository quality gate | PASS | Fresh 2026-10-14 gate, public/manual evidence, privacy/diff/workflow checks |
| 26 | Locked specs | PASS | All four raw-byte comparisons to 8e2029a |
| 27 | Scope | PASS | M7 hardening only; no prohibited functionality or M8 |
| 28 | Milestone commit/push/clean tree | VERIFY AFTER COMMIT | Single milestone commit and exact-commit hosted CI checked in completion report |
| 29 | Structured report / stop | PASS | Pre-commit record plus final completion report; stop before M8 |

The disposable long-label project, its two runs and positively identified private
artifact prefix were cleaned; the earlier stack was restored to Demo and its
original seed fingerprints verified. The final 2026-10-14 stack remains read-only
on loopback with only PostgreSQL and the production web service running.

The external and manual prerequisites are complete. Final M7 PASS additionally
requires successful hosted CI on the exact single pushed commit and a clean tree.
STOP before M8.
