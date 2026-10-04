# M4 milestone verification

MILESTONE: M4 — Mode B Performance + Calibration + Errors

STATUS: Scientific, operational, regression, browser and privacy gates PASS.
The final milestone reply records the single commit, push and remote verification.
STOP BEFORE M5.

## IMPLEMENTED

Fully labeled current uploads now proceed from explicit Mode B compatibility
review through Analyze to saved Overview, Performance, Calibration and Classes &
Errors. Existing data, missingness, prediction and confidence analyses remain.
New pages expose true class composition, supported metric comparisons, persisted
historical/current reliability diagrams and bounded canonical error examples.

## ARCHITECTURE / SCIENTIFIC DECISIONS

No locked decision changed. The existing PostgreSQL worker, frozen baseline,
upload/parser/storage boundaries and fenced publication are extended. Current
inference happens once; existing M3 scientific analysis is reused unchanged.
Historical metrics/calibration are read from the hash-verified M2 results artifact
and checked against snapshot metadata, never reevaluated under current code.
Only the worker calculates statistics. See methodology.md for metric definitions,
signed absolute-unit deltas, absent-class comparability and support policy.

No refit, model change, calibration verdict, combined score, performance
significance test, severity, retrain/deploy recommendation or M5 analysis is added.

## TESTS AND CHECKS

Complete successful gate:

```powershell
./scripts/m4-gate.ps1 -ProjectName modelmedic-m4-verified -ApiPort 18008 -FrontendPort 15181
```

- Ruff PASS; formatting PASS (61 Python files).
- Strict mypy PASS (43 source files).
- Full pytest PASS: 145 tests — 92 unit/scientific and 53 real PostgreSQL tests.
- Added 20 scientific tests and 7 PostgreSQL cases; prior M0–M3 tests pass.
- The obsolete M3 assertion that Mode B analysis returns 409 now requires 202;
  its frozen categorical-validation guarantee is preserved. No Mode A test was
  weakened. Explicit Mode A claim/schema, stage and UI regressions pass.
- Frontend lint, TypeScript, Vitest (32 tests, including 8 new) and build PASS.
- npm audit PASS: zero vulnerabilities.
- M0 service/proxy/heartbeat/dummy/duplicate smoke PASS.
- M1 complete setup without automatic training smoke PASS.
- M2 all 12 target/model/weighting combinations PASS.
- M3 binary and multiclass Mode A smoke PASS.
- M4 binary and multiclass Mode B, each with full support and absent current
  classes, PASS. Insufficient positive/non-positive calibration is exercised.
- Privacy scanner, diff checks, final candidate review and locked-byte check PASS.

The initial complete gate found that an empty false-positive example selection
used an untyped Arrow index array. The M4 endpoint now supplies int64 indices for
empty and nonempty selections. The full gate was rerun successfully afterward;
the browser verified empty FP and exactly 50 FN examples.

## DOCKER / SERVICES

Isolated project modelmedic-m4-verified: API 18008, frontend 15181, private
PostgreSQL 17 and dedicated worker. Compose configuration, backend/frontend/test
builds, explicit migrations, database health, readiness, frontend proxy and worker
heartbeat passed. API and worker use the same image and artifact volume. Prior
milestone stacks were not modified. Precommit images honestly record approved M3
SHA and dirty source state; clean-commit runtime provenance is checked after the
milestone is committed. No public deployment is claimed.

## DATABASE / MIGRATIONS

Additive 0005_m4 follows 0004_m3. Normal metric columns retain baseline/current,
delta, support, scope, class, availability and reasons. Calibration stores support
and nested historical/current bin evidence. Errors store aggregates and canonical
row references only. Run results persist true class composition. Result tables
cascade with run deletion. Existing migration/metadata round-trip checks pass.
Triggers prevent result updates and insertion into already analyzed runs.

## MODE B VALIDATION

Target must exist, every row must be labeled and every label must belong to the
frozen class list. Partial/unknown labels reject without Mode A fallback. The mode
is declared before Analyze. Existing streamed byte limits, server-generated paths,
reserved-column rejection, canonical IDs/hash/schema, frozen feature compatibility
and missing-value policy remain covered by regression tests.

## PERFORMANCE

Binary locked metrics use the explicitly frozen positive class, including when
its probability column is first. Multiclass metrics and per-class results use the
full frozen order. Known-answer accuracy, balanced accuracy, precision/recall/F1,
ROC-AUC, average precision, log loss, binary and multiclass Brier, macro/weighted
and per-class fixtures pass. Each comparison persists baseline/current values,
signed current-minus-baseline delta in metric units, supports, availability and
reason. Undefined values are null with a reason, never fabricated zero/NaN.

Performance starts with the required sampling-variation limitation. True class
mix appears before grouped Classification, Ranking and Probability quality tables.
Tables show all seven required columns and neutral deltas. The overview retains
existing data/model-behavior groups, adds four measured metrics and a probability-
quality/calibration card, with the required Mode B banner and no health card.

## ABSENT-CLASS HANDLING

Zero-support current classes remain in the frozen space. Macro and balanced-
accuracy comparisons become unavailable with explicit class-set reasons; invalid
ranking metrics are unavailable. Valid accuracy/per-class/probability values remain
visible. Full-space log loss/Brier preserve the required class-composition caution.
True class shares/counts use held-out baseline labels versus current labels and
are distinct from predicted shares. Unit, PostgreSQL, smoke and browser absent-
class cases passed, including unavailable curves and zero-support matrix rows.

## CALIBRATION

Baseline curves remain the historical M2 artifact values. Current curves reuse
locked quantile bins: 3/5/8/10 at 40/100/250/500, combining tied boundaries.
Each binary/OvR curve requires 20 positive and 20 non-positive observations.
Below 250, the limited-support warning is visible. All threshold boundaries,
support guards, frozen multiclass order, absent-class unavailability and bin-count
sums pass. The chart uses mean probability versus observed frequency, fixed 0–1
axes and y=x; both series, explicit sample sizes, focus/tooltip bin support and
tables are present. Brier is labeled probabilistic prediction quality. No ECE,
recalibration action or calibration verdict exists.

## CLASSES / ERRORS

Baseline/current counts and row-normalized confusion matrices use frozen order
and a neutral single hue. Zero-support rates are unavailable. Binary TP/TN/FP/FN
use the selected positive class, with FP/FN example views. Multiclass common
confusion pairs show counts, actual-class support/rates and inspectable examples.
Canonical row references are capped at 50 per view. API retrieval validates source
hash/schema and projects only included model features. Excluded identifiers and
target cannot reappear; arbitrary views are rejected and HTML-like cells escape.
No full error rows are stored in PostgreSQL. Real empty/bounded views passed.

## MODE A REGRESSION

All original unlabeled scientific and lifecycle tests pass. Mode A skips
PERFORMANCE/CALIBRATION stages and returns its original unavailable contracts.
No current outcome metric, calibration, confusion/error/slice analysis, degradation
claim or retrain recommendation appears. Binary/multiclass real-stack smoke and
all four unavailable browser pages passed with no fake charts/tables.

## IMMUTABILITY / WORKER

Mode B stages: VALIDATING, PREDICTING, DATA_DRIFT, MISSINGNESS, PREDICTION_DRIFT,
CONFIDENCE, PERFORMANCE, CALIBRATION, PERSISTING, COMPLETE. No fake percentages.
Only an explicit Analyze action queues work. Duplicate active analysis is rejected.
Feature/labeled rows, result object hash/provenance, ANALYZED state and terminal
job state publish atomically under the existing fence. Stale ownership rolls back
every result table; corrupted historical results fail without partial exposure.
Reloaded API/artifact outputs are identical. Fitted preprocessing/model bytes and
historical baseline values remain unchanged. Analyzed upload/reanalysis is blocked.

## BROWSER / PRIVACY / SECURITY

Actual browser details/date/notes, local file chooser/upload, separate validation
progress, explicit Mode B review/Analyze, meaningful analysis stages, Overview,
Performance, Calibration, Classes & Errors, count toggle, 50-row FN and empty FP
views, multiclass selector/pairs, absent-class warnings and unavailable metrics
were checked. Calibration points are keyboard focusable with bin counts. Route
focus reaches main-content. Performance/Calibration/Errors at 320px keep document
width 305px, with limitations and internally contained tables. Mobile menu works.
Saved results reload identically and expose no upload/reanalysis controls.

Smoke and browser synthetic projects, current imports, baselines and exact private
artifact prefixes were removed. The isolated M4 database has no remaining projects.
Screenshots/logs/temporary CSV remain ignored under .cache, outside commit candidates.
Candidate scanning and manual diff review found no .env, credentials, private data,
generated datasets/model objects or build output. No new external transmission or
public exposure is introduced. Existing demo guard behavior remains unchanged.

## LOCKED SPECIFICATIONS

All four locked specification files are byte-identical to their original 8e2029a
versions. Relevant PRD/architecture/UI/milestone sections were reread before edits.
No locked methodology, architecture, wording, history or milestone decision changed.

## KNOWN ISSUES

No blocking M4 issue. The pinned Starlette/httpx TestClient combination still emits
its existing deprecation warning while tests pass. Failed cleanup of an old private
artifact prefix can still leave an inaccessible prefix until draft project deletion;
the pre-existing limitation is preserved. Production deployment and capacity are
not claimed. Slices, trends and report generation remain M5.

## GIT

Approved parent: f7d49cf295ef7ef3bbfa347f0903e7fe93da3348. The initial main working
tree and live origin/main were clean and equal to that commit. Exactly one requested
commit: `feat: add labeled performance calibration and error analysis`.
No prior commit is amended or rewritten. Noreply identity is preserved. The final
reply records commit SHA, verified origin/main equality and clean working tree.

## Every M4 gate item

| Gate item | Result |
|---|---|
| Approved clean M3 parent/live origin and four locked specs verified before edits | PASS |
| Relevant locked PRD/architecture/UI/milestone sections reread | PASS |
| Complete labeled current workflow and explicit Mode B before Analyze | PASS |
| Partial/unknown labels rejected with no Mode A fallback | PASS |
| Existing safe upload/canonical/frozen-schema/missing-policy guarantees | PASS |
| Exact Mode B stages; Mode A skips labeled stages; no fake percentage | PASS |
| Locked binary metrics with selected positive class and remapped probabilities | PASS |
| Locked multiclass/per-class metrics, support and frozen class order | PASS |
| Baseline/current/signed-unit delta/support/status/reason persisted | PASS |
| Undefined metrics unavailable with reasons; no fake zero/NaN | PASS |
| Absent-class macro/balanced/ranking comparability guards | PASS |
| Full-space probability metrics and required class-composition caution | PASS |
| Required performance uncertainty limitation; no significance/severity/score | PASS |
| Historical baseline metrics/calibration read, verified and never recomputed | PASS |
| Calibration thresholds, event-support guards, limited-support warning/bin counts | PASS |
| Frozen multiclass OvR selection and absent-class unavailable curves | PASS |
| Binary TP/TN/FP/FN, confusion counts and actual-class normalized rates | PASS |
| Multiclass common pairs/counts/support/rates | PASS |
| Canonical row-only references, 50/view, feature projection and escaped text | PASS |
| True held-out/current class mix separate from predicted distribution | PASS |
| Required Mode B banner, overview metric group and calibration card | PASS |
| Performance limitation first, class mix before seven-column neutral tables | PASS |
| Reliability axes/diagonal/two series/equal points/focus/support tables | PASS |
| Neutral single-hue matrices/count toggle/error views | PASS |
| Atomic fenced worker publication, duplicate prevention and no partial results | PASS |
| Immutable reload, model state/baseline preservation and integrity failure guards | PASS |
| Mode A contains no measured outcomes/errors/slices/degradation/retrain claims | PASS |
| Scientific known-answer/order/undefined/absent/calibration/error tests | PASS |
| PostgreSQL lifecycle/immutability/fencing/failure/privacy tests | PASS |
| Real binary/multiclass Mode B full/absent/insufficient-support Compose flows | PASS |
| Real binary/multiclass Mode A Compose regressions | PASS |
| Complete M0/M1/M2/M3 regression suites and M2 all 12 combinations | PASS |
| Ruff/format/mypy/full pytest and actual PostgreSQL | PASS |
| Frontend lint/TypeScript/tests/build/npm audit | PASS |
| Compose config/Docker builds/migrations/services/proxy/heartbeat/smoke | PASS |
| Browser flow/unavailable/absent/responsive/keyboard/route-focus checks | PASS |
| Synthetic verification project and artifact cleanup | PASS |
| Privacy/secret/candidate/diff review and byte-identical locked specs | PASS |
| No M5 Slices/Trends/Reports or health/retrain/deploy scope creep | PASS |
| Existing known issues preserved and reported | PASS |

Publication checks (single requested commit, approved parent, noreply author,
origin/main equality, clean tree and clean-build provenance) are recorded in the
final response after execution; they are not inferred from precommit test results.

NEXT = M5 — Feature Diagnostics + Slices + Trends + Reports. STOP BEFORE M5.
