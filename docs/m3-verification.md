# M3 milestone verification

MILESTONE: M3 — Monitoring Core + Mode A

STATUS: Scientific, operational, regression, browser and privacy gates PASS.
The final milestone reply records the single commit, push and remote verification.
STOP BEFORE M4.

## IMPLEMENTED

Established project overview and monitoring history; run name/date/notes; safe
streamed current CSV upload; canonical Parquet and frozen-schema compatibility
review; explicit Mode A analysis through the existing leased PostgreSQL worker;
immutable feature/missingness/prediction/confidence output and chart values;
dedicated Feature Detail and all four label-dependent unavailable explainers.

## ARCHITECTURE / SCIENTIFIC DECISIONS

No locked decision changed. DATASET_VALIDATE handles current compatibility before
the explicit MONITORING_ANALYZE action. Each run binds its exact established
baseline_snapshot_id. Drift reads all valid raw baseline observations before
imputation/scaling/missing-category insertion/OHE. Prediction/confidence read the
hashed persisted M2 held-out reference. Only the worker loads trusted joblib and
calls frozen prediction methods; no fitting occurs in monitoring.

M3 statistical/serialization choices are documented in methodology.md, including
the explicit pinned SciPy parameters, pooling membership, BH family and stored
bin definitions. The API/frontend render stored values rather than recalculating.
Numeric finite bins include the baseline maximum; explicit overflow bins retain
out-of-range observations. Tiny nonzero p-values display scientific notation.

## TESTS AND CHECKS

The complete final run used:

```powershell
./scripts/m3-gate.ps1 -ProjectName modelmedic-m3-release -ApiPort 18007 -FrontendPort 15180
```

- Ruff PASS; format check PASS (55 Python files).
- Strict mypy PASS (40 source files).
- Full pytest PASS: 118 tests, including 72 unit/scientific and 46 real PostgreSQL tests.
- Every existing M0/M1/M2 test remains passing; only the obsolete M2 assertion that
  monitoring has no route was updated to require valid M3 run details (422).
- Frontend ESLint, TypeScript, Vitest (24 tests) and production build PASS.
- npm audit PASS: zero vulnerabilities.
- M0 real services/proxy/heartbeat/dummy/duplicate smoke PASS.
- M1 complete setup without automatic training smoke PASS.
- M2 all 12 binary/multiclass × classifier × weighting combinations PASS.
- M3 real-stack binary and multiclass unlabeled workflows PASS.

## DOCKER / SERVICES

Final isolated Compose project: modelmedic-m3-release. API 18007; frontend 15180;
PostgreSQL remains private on its internal port. API/worker share the backend
image and artifact volume. Compose config/build, explicit migrations, PostgreSQL
health, API readiness, frontend proxy and worker heartbeat passed. The initial
M3 gate also ran on modelmedic-m3-verified (18006/15179). Prior milestone stacks
were not modified. Clean-commit image provenance is checked after publication.

## DATABASE / MIGRATIONS

Additive 0004_m3: monitoring metadata/reference/provenance/results, history index,
per-feature scalar evidence plus nested JSONB, frozen-binding and published-result
guards. M0 migration/metadata round-trip tests pass. Fenced finalization seals run
and feature outputs in one transaction. Insertion/update of published feature
evidence and changes to analyzed run results/bindings are rejected. Run deletion
blocks active work and supports retry after external cleanup failure.

## MODE A VALIDATION

Minimum 50 rows; shared strict parser/missing policy; server-controlled paths;
streamed byte-limit enforcement; reserved column rejection; stable internal row IDs;
hash/schema metadata. Missing required features and unsafe numeric values block.
Extras are allowed/warned/ignored for inference. Frozen categorical semantics
retain raw spellings. Coercion counts, new categories and warnings are persisted
and displayed. Partial/unknown labels block. Valid complete labels declare Mode B,
whose analysis is explicitly unavailable in M3; no silent Mode A fallback.

## NUMERIC DRIFT / CATEGORICAL DRIFT / MISSINGNESS / BH-FDR

Numeric KS/Wasserstein, observed n guard, tied/discrete caution and descriptive
outside-range share pass deterministic fixtures. Categorical base-2 JS, dynamic
sample-aware pooling, internal collision-safe IDs, smallest retained-category
merge, membership/expected-cell persistence and insufficient-data rules pass.
Missingness zero/zero skipping, chi-square/Fisher switching, percentages and pp
delta pass. Combined feature distribution/missingness BH matches the trusted
reference vector, excludes invalid/no-p tests and persists family size.

## PREDICTION DRIFT / CONFIDENCE

Frozen class order and raw shares/deltas/JS/valid categorical test are persisted.
Prediction wording describes output distribution change, without correctness
claims. Confidence uses max class probability, persisted held-out confidence,
mean/median, fixed [0,1] histograms and KS. Both comparisons remain outside feature
BH. Tests verify reversed probability class order and unchanged fitted
imputer/scaler/encoder/classifier state under current inference.

## CLAIM-SAFETY VERIFICATION

Automated backend result-template and frontend unavailable-screen tests reject
forbidden degradation/failure/calibration/retrain language and current outcome
metric keys. The required ground-truth limitation and confidence limitation are
visible. No current accuracy/F1/AUC/log loss/Brier/confusion/errors/slices or
calibration analysis is produced. Full report export remains M5 scope.

## BROWSER / PRIVACY / LOCKED SPECIFICATIONS

Real browser verification on the final build: details/date/notes, actual file
chooser/upload, separate validation progress, pre-analysis mode/compatibility
review, explicit analysis/progress, Overview, all Data tabs, dedicated numeric and
categorical Feature Detail, Predictions, Confidence and all four Unavailable
pages. Immutable reloads and absent upload/reanalysis controls verified. Data and
Feature Detail at 320px keep document width 305px, route focus and limitations.
Synthetic projects, current imports, baselines and private artifact prefixes were
cleaned after inspection; screenshots/logs stay ignored under .cache.

Privacy scanner and complete commit-candidate diff review pass: no environment
file, credentials, private data, generated datasets/model objects or build output.
All four locked specification files are byte-identical to their 8e2029a originals.

## KNOWN ISSUES

No blocking M3 issue. The prior M2 limitation remains: failed old-artifact cleanup
can leave an inaccessible private prefix until draft project deletion. The pinned
Starlette TestClient/httpx combination emits a deprecation warning; tests pass.
Deployment capacity/production hardening and full report export are not claimed.

## GIT

Approved parent: 2b631f32d57b694fdae2e12683257f9ff98ee40b. One requested milestone
commit: `feat: add unlabeled reliability monitoring and drift analysis`.
No prior milestone is amended or rewritten. Noreply identity is preserved.
The final reply records commit SHA, origin/main equality and clean working tree.

## Every M3 gate criterion

| Criterion | Result |
|---|---|
| Approved clean M2 parent and live origin verified before edits | PASS |
| All four relevant locked-spec sections reread; original bytes preserved | PASS |
| Run name/date/notes, exact snapshot binding and deterministic history | PASS |
| Safe streamed upload, byte cap, reserved namespace, canonical IDs/hash/schema | PASS |
| Frozen features/numeric/categorical compatibility and visible diagnostics | PASS |
| Minimum 50 rows, Mode A detection, partial/unknown-label rejection | PASS |
| Valid Mode B recognized without M4 analysis | PASS |
| Existing leased/fenced worker, exact meaningful stages, no fake percent | PASS |
| No partial result visibility before atomic finalization | PASS |
| Raw observed-value drift boundary; missingness separate | PASS |
| Numeric KS/Wasserstein/n/ties/range and deterministic fixtures | PASS |
| Categorical JS/dynamic pooling/merge/expected counts/raw membership | PASS |
| Missingness zero-zero/chi-square/Fisher/percent/delta fixtures | PASS |
| Combined valid feature BH q=.05, exclusions and persisted family | PASS |
| Explicit locked/pinned statistical-library parameters | PASS |
| Frozen-class prediction drift from persisted held-out reference | PASS |
| Max-probability confidence from persisted held-out reference; fixed axis | PASS |
| Prediction/confidence tests excluded from feature BH | PASS |
| Worker-persisted plot data; no API/frontend statistical recomputation | PASS |
| No monitoring refit; fitted preprocessing/model state unchanged | PASS |
| Duplicate prevention, failure isolation, fencing and immutable publication | PASS |
| Complete locked Mode A UI, references and Evidence Frame | PASS |
| Four label-dependent pages explicitly Unavailable | PASS |
| Automated forbidden-claim/result-schema checks | PASS |
| Binary and multiclass real Compose workflow and immutable reload | PASS |
| Complete M0/M1/M2 scientific/platform/frontend/12-combination regressions | PASS |
| Ruff, format, mypy, full pytest/PostgreSQL | PASS |
| Frontend lint, TypeScript, tests, build and audit | PASS |
| Compose config/build/migrate/services/proxy/worker/smoke | PASS |
| Real browser workflow, responsive containment and final display fixes | PASS |
| Synthetic data/artifact cleanup | PASS |
| Privacy/secret/generated-artifact review; full diff and locked bytes | PASS |
| No M4 scientific functionality or locked-decision change | PASS |

NEXT = M4 — Mode B Performance + Calibration + Errors. STOP BEFORE M4.
