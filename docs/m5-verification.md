# M5 milestone verification

MILESTONE: M5 — Feature Diagnostics + Slices + Trends + Reports

STATUS: Scientific, PostgreSQL, regression, Compose, browser and privacy gates PASS.
The final reply records the single commit, clean-build provenance and live remote SHA.
STOP BEFORE M6.

## IMPLEMENTED

Saved monitoring results now support complete Feature Detail and Reliance × change,
explicit categorical slice analysis, one-signal Trends, immutable Reliability
Reports, and a static reviewed Methodology page with a searchable glossary.
Existing project, baseline and Mode A/B workflows are preserved.

## ARCHITECTURE / SCIENTIFIC DECISIONS

No locked decision changed. M5 extends the existing PostgreSQL leased worker,
artifact storage and fenced publication. API routes select persisted evidence;
they do not load models or calculate scientific statistics. Slice workers apply
the frozen pipeline without fitting and reuse existing V1 labeled metrics.
Trends do not create a second scientific result dataset. Reports use fixed
reviewed templates, never an LLM or a server-side PDF engine.

## TESTS AND CHECKS

Final gate command:

```powershell
./scripts/m5-gate.ps1 -ProjectName modelmedic-m5-verified -ApiPort 18009 -FrontendPort 15182
```

The final complete gate executed successfully after the final implementation fixes:

- Ruff PASS; format check PASS (72 Python files); strict mypy PASS (51 sources).
- Full pytest PASS: 167 tests, including 107 unit/scientific and 60 real
  PostgreSQL integrations; no integration skips. One existing warning remains.
- Frontend lint, TypeScript, 38 tests in six files and production build PASS.
- npm audit PASS: zero vulnerabilities.
- Compose configuration/build, explicit migrations, four services, readiness,
  frontend proxy, worker heartbeat and dummy/duplicate job smoke PASS.
- M1 complete setup without automatic training PASS.
- M2 all 12 supported target/model/weighting combinations PASS.
- M3 binary/multiclass Mode A and M4 binary/multiclass Mode B full/absent support PASS.
- M5 real B-A-B history, all signal groups, idempotent slices and immutable reports
  PASS; all four services restarted, then persisted hashes verified again PASS.
- Exact synthetic fixture and private artifact cleanup PASS.
- Privacy scan PASS: 132 candidate files; raw-byte locked-spec check and full
  candidate/diff review PASS.

New deterministic coverage includes the 29/30-row boundary; raw category/null distinctions; binary
and multiclass metric availability; separate distribution/missingness evidence;
Mode A gaps; selectors and chronological ties; template changes; historical report
creation; concurrent slice idempotence; database immutability; corrupt sources;
fencing rollback; additive cleanup; and report/Methodology frontend behavior.

M4's obsolete Mode B slice placeholder assertions now expect the M5 AVAILABLE
contract. Their scientific, lifecycle and claim-safety assertions remain intact.
The existing Feature Detail mock now supplies the dedicated endpoint's payload.
The prior fenced Mode B rollback test additionally verifies no report is published.

## DOCKER / SERVICES

Isolated project `modelmedic-m5-verified`: API 18009, frontend 15182, private
PostgreSQL 17 and dedicated worker. The gate builds runtime/frontend/test images,
checks Compose configuration, explicitly migrates, exercises readiness, proxy,
heartbeat and real jobs, then restarts all four services and verifies stored M5
payload hashes. Other milestone containers are not altered. Precommit images
honestly record the approved M4 SHA and dirty source state; postcommit runtime
provenance is checked using the clean milestone SHA.

## DATABASE / MIGRATIONS

Additive `0006_m5` follows `0005_m4`. Only slice analyses, slice results and stored
reports are added. Unique `(run_id, feature_id, methodology_version)` bindings
prevent repeat work. Bindings, counts, states and versions are normal columns;
nested class supports/metric availability and report documents use JSONB as
specified by locked Architecture §27. No core metric storage is replaced.
Triggers reject sealed slice changes, late slice inserts and report updates.
Derived rows cascade with run deletion; associated slice jobs are removed.
Existing migration round-trip and model/metadata checks remain in the full suite.

## FEATURE DIAGNOSTICS

Feature Detail exposes frozen name/type, separate statuses, warnings, original
baseline/current visualization, test/statistic, raw/adjusted p, BH family size,
sample sizes, Wasserstein/JS, pooling membership, missingness delta, categories,
range and held-out permutation reliance. Data comparisons retain all valid
baseline rows. The fixed interpretation includes exactly:

> ModelMedic does not claim this feature change caused any change in performance.

Reliance × change presents separate drift, missingness and baseline reliance,
including negative values and their noncausal interpretation. It creates no
combined score, risk label or severity ranking.

## SLICES

Only analyzed Mode B runs and included frozen categorical features are eligible.
An explicit action creates `SLICE_ANALYZE`; repeats return the existing analysis
even while pending or failed. Worker stages are VALIDATING, PREDICTING, SLICES and
PERSISTING under the existing ownership fence. Snapshot/config/schema/class/type,
canonical/model/manifest hashes and artifact environment are verified. All rows
metrics must match the saved current metrics before atomic publication.

Results retain All rows, n, frozen class support, valid metrics and reasons.
Raw whitespace variants and literal `null` remain values, distinct from missing.
Display uses deterministic category order with explicit PostgreSQL C collation,
never worst-performance order. At n <30, no metrics are calculated:

> Insufficient sample size for stable slice analysis.

The table retains insufficient groups; a selected-metric dot plot omits them and
shows the overall reference. The persistent limitation is exactly:

> Slice comparisons are exploratory. ModelMedic does not perform significance testing or multiplicity correction across slices. Apparent differences may reflect sampling variation. This is not a fairness audit.

## TRENDS

One selected stored signal supports target-specific performance, Brier/Log Loss,
confidence mean/median, selected frozen predicted-class share, selected numeric
KS/categorical JS, and missing %. Feature and class selectors enforce frozen
eligibility. Runs sort by Monitoring Date, Creation Timestamp and Run ID.
Mode A outcomes remain null with explicit label reasons. Markers and a support/
status/adjusted-p table preserve gaps without connecting lines or interpolation.
References are historical held-out values or all-row baseline missingness;
KS/JS never receive a fabricated baseline self-comparison. Mixed methodology
versions show a caution and never trigger recalculation. No forecast, regression,
overall reliability trend, bad zones or improving/declining verdict is added.

## REPORTS

Reports are persisted during fenced run finalization. Older analyzed runs receive
their first stored report once, from saved facts only. Subsequent reads retain
the original template, methodology, source/report code versions and generation
timestamp even after a future-template change. Later slices are separately
versioned additive sections and never rewrite the core payload.

The exact 12 sections are Project; Baseline; Run metadata; Schema/compatibility;
Data changes; Prediction behavior; Confidence; Performance; Calibration;
Classes & errors; Slices if created; Limitations. Mode A unavailable sections
remain with their reason. Findings explicitly render Measured, Result, Evidence,
May conclude and Cannot conclude in that order, independent of JSONB key order.
All nine mandatory limitations and the exact no-language-model footer remain.
Full example rows and excluded identifiers are not copied into reports.

Reports use section links, one column, monochrome print styles, hidden navigation
and record alternatives for wide tables. Print / Save as PDF calls browser print.
The print-layout preview uses the identical stylesheet for inspectable browser
verification. Actual native print/PDF dialog inspection is unavailable in the
in-app browser; no saved PDF or paper pagination is claimed. The print call is
unit-tested and the shared layout was visually checked at desktop and 320px.

## METHODOLOGY / GLOSSARY

The static reviewed page covers workflow, stratified split/fold-local CV,
preprocessing/missing policy, metrics, KS, Wasserstein, JS, contingency pooling,
chi-square, Fisher exact, BH/FDR, confidence, calibration, raw-feature permutation
reliance, slices, guardrails and limitations. The searchable glossary has 21
terms. Guardrail values and wording match the locked V1 methodology. No API
freeform content, model recommendation or M6 public demo work is added.

## IMMUTABILITY

Core run object bytes/hash, baseline snapshot and model remain unchanged after
slice publication. Concurrent/repeat requests create one analysis/job. Lost
ownership rolls back every derived row; corrupt sources publish no partial rows.
Report updates/late slice inserts fail at the database. Template changes do not
regenerate historical reports. Trends read saved values only. Restart/reload
verification compares stored core, report and slice hashes.

## MODE A / MODE B REGRESSION

The final gate includes all M0–M4 tests and real smoke workflows: foundation;
complete setup without automatic training; all 12 target/model/weighting baseline
combinations; binary/multiclass Mode A; binary/multiclass Mode B with full and
absent class support. Existing probability quality, calibration, errors,
label/schema, lifecycle, upload and claim-safety guarantees are preserved.

## BROWSER VERIFICATION

Actual browser checks cover Feature Detail evidence/visualization, separate
missingness and reliance, explicit slice creation through the real worker,
All rows/support/29-row unavailability/raw categories, saved reloads, Trends
signals/selectors/B-A-B outcome gap, report sections/limitations/reload/additive
slices, and Methodology/glossary search. Route focus reaches main-content.
Keyboard controls show a visible focus ring. At 320px, document width is 305px;
tables and readable charts scroll inside their own containers. Scientific
warnings remain visible. Print preview hides navigation, uses black tables and
wide-table record alternatives, and fits 320px after verification fixes.
The real history uses one methodology version; the mixed-version caution is
exercised by PostgreSQL and frontend fixtures rather than invented browser data.

## PRIVACY / SECURITY

Only synthetic disposable verification data is used. Scripts remove their exact
stored project UUID, associated runs/derived rows and private artifact prefix.
Screenshots/logs/temporary fixtures stay ignored in .cache. Candidate scanning
and full diff review check for .env, credentials, private data, generated/model
artifacts and accidental files. No new external transmission, public deployment,
health score, retrain/deploy control, LLM report service or M6 implementation is
introduced. Existing Demo Mode compatibility guards remain unchanged.

## LOCKED SPECIFICATIONS

All four locked specifications are checked as raw bytes against their original
`8e2029a` versions. Relevant locked sections were reread before edits. No locked
methodology, architecture, wording, milestone or Git-history decision changed.

## KNOWN ISSUES

The existing Starlette/httpx TestClient deprecation warning remains. The old
inaccessible artifact-prefix cleanup limitation is preserved; M5 does not redesign
unrelated cleanup. Native print dialog/PDF pagination cannot be inspected by this
browser automation; shared print layout verification is described above.

## GIT

Approved parent: `6b2263133d0606093b4017ccf40d574d37d56f7e`. Before edits, main and
live origin/main were clean and equal to it. Exactly one requested milestone
commit is permitted: `feat: add slices trends and deterministic reliability reports`.
No prior history is rewritten. The final response records the noreply identity,
commit SHA, verified parent/live remote equality and clean working tree.

## Every M5 gate item

| Gate item | Result |
|---|---|
| Approved clean M4 parent, main and live origin/main verified before edits | PASS |
| Relevant four locked specifications reread; no locked decisions changed | PASS |
| Complete Feature Detail fields, visualization, warnings and fixed interpretation | PASS |
| All-row data reference; distribution and missingness statuses remain separate | PASS |
| Exact feature noncausal sentence and permutation reliance interpretation | PASS |
| Reliance × change exposes separate drift/missingness/reliance; no composite/severity | PASS |
| SLICE_ANALYZE uses existing PostgreSQL claim/lease/heartbeat/fencing | PASS |
| Only saved Mode B and included frozen categorical features eligible | PASS |
| Unique run/feature/method binding; concurrent/pending/failed repeats return existing | PASS |
| Frozen snapshot/config/schema/class/type/hash/environment source verification | PASS |
| Frozen inference without fitting; overall current metrics match core results | PASS |
| All rows, raw slices, distinct missing values, n and frozen class support | PASS |
| n <30 calculates no metrics and retains exact unavailability reason | PASS |
| Valid metric set and current availability reasons including absent-class guards | PASS |
| Additive fenced persistence; core results/model/snapshot/report unchanged | PASS |
| Exact exploratory/no-testing/no-multiplicity/no-fairness limitation persists | PASS |
| Slices selector, explicit action, prior features, table and All rows reference | PASS |
| One selected metric dot plot; small slices omitted only from plot; no worst ranking | PASS |
| Every supported target-specific Trends group/signal and frozen selectors | PASS |
| Date/timestamp/ID ordering, including deterministic ties | PASS |
| Mode A outcome gaps retained; no connected lines, smoothing or interpolation | PASS |
| No forecast/regression/improvement verdict/bad zones/overall reliability score | PASS |
| Meaningful saved baseline references; no KS/JS self-comparison | PASS |
| Trend table values/support/status/reasons/adjusted p from persisted facts | PASS |
| Methodology-version caution in PostgreSQL/frontend fixtures | PASS |
| Reports saved at fenced finalization; older runs create once from stored facts | PASS |
| Immutable report template/method/code/timestamp and future-template-change test | PASS |
| Exact 12 sections, Mode A unavailable reasons and Mode B measured sections | PASS |
| Explicit five-field finding order and all nine mandatory limitations | PASS |
| Separately versioned later slices never rewrite core report | PASS |
| Exact report footer; no LLM, causal/retrain/health verdict or copied example rows | PASS |
| Single-column report, jumps, monochrome print CSS, hidden nav and table alternatives | PASS |
| Browser print call tested; identical print-layout preview inspected desktop/320px | PASS |
| Static locked Methodology topics and searchable glossary; no API freeform content | PASS |
| Minimal additive schema/JSONB as specified; migrations/round-trip/cascade checks | PASS |
| Scientific, behavioral and actual PostgreSQL lifecycle/failure/immutability tests | PASS |
| Complete M0–M4 regressions; earlier scientific and claim-safety tests preserved | PASS |
| Real B-A-B Compose flow, repeat slices, all signals, immutable report/restart hashes | PASS |
| Browser Feature Detail/Slices/Trends/Report/Methodology and saved-page reloads | PASS |
| Keyboard route/control focus, 320px containment and retained scientific warnings | PASS |
| Ruff/format/mypy/full pytest with actual PostgreSQL | PASS |
| Frontend lint/TypeScript/tests/build and zero-vulnerability npm audit | PASS |
| Compose config/build/migrations/services/proxy/heartbeat and complete real smoke | PASS |
| Exact synthetic projects/runs/derived rows/private artifact prefixes cleaned | PASS |
| Privacy/secret/candidate/full diff review; no env/credentials/generated artifacts | PASS |
| Four locked files byte-identical to 8e2029a | PASS |
| No M6 demo/deployment, health/retrain/deploy controls, server PDF or LLM service | PASS |
| Existing known issues preserved and reported | PASS |

Publication checks (exactly one requested commit, approved parent, noreply identity,
live origin/main equality, clean working tree and clean-build provenance) are
recorded in the final reply after execution. They are not inferred from test results.

NEXT = M6 — Full UI/UX Integration + Public Demo Mode. STOP BEFORE M6.
