# M6 verification record

MILESTONE: M6 — Full UI/UX Integration + Public Demo Mode.

STATUS: PASS for implementation and acceptance verification. The final executable
gate was restarted from its beginning after the final Demo boundary fix and
finished with exit code 0. Earlier successful runs are not the final gate evidence.
Git publication and the resulting SHA are recorded in the completion report.

## Implemented / design system / UI/UX conformance

The existing application now shares semantic scientific status chips, the five-field
Evidence Frame, project/run navigation, Demo mutation controls and actionable error
states. It retains the Clinical Reliability Lab light presentation, Inter UI,
selective JetBrains Mono statistics, restrained panels, visible focus and separate
indigo Baseline / teal Current series. DETECTED is amber; NOT DETECTED is neutral
slate; INSUFFICIENT DATA and UNAVAILABLE are neutral gray. Text and icons convey
status without color. No new scientific status or health/severity verdict exists.

Established projects expose Overview / Baseline / Runs / Trends. Draft setup has
grouped DATA / CONFIGURE / TRAIN / LOCK steps. Monitoring navigation groups WHAT
CHANGED and NEEDS LABELS; Mode A label-dependent pages remain accessible with the
slashed-circle unavailable explanation. Compact navigation preserves these pages.
Reviewed backend presentation templates provide interpretation boundaries without
changing persisted results or calculating scientific conclusions in the frontend.

Tables retain raw category spellings, support, unavailable reasons and frozen class
order. Distribution views use shared normalized bins or paired category shares;
calibration exposes equal-size focusable points and exact bins/support; permutation
importance preserves negative values and SD whiskers; CV shows five observed folds;
trends show one saved signal with gaps. Cross-feature Wasserstein ranking is removed.

## Tests and checks

Final command, executed against the frozen final implementation:

```powershell
./scripts/m6-gate.ps1
```

The complete local transcript is in ignored `.cache/m6-final-postfix-gate.log`.
The script chains every M0–M5 gate before the M6 checks; none was skipped.

| Check | Final result |
| --- | --- |
| Ruff | PASS |
| Ruff formatting | PASS — 78 files already formatted |
| Configured mypy | PASS — 53 source files |
| Full pytest against PostgreSQL | PASS — 173 tests, including 61 integration tests |
| Frontend ESLint | PASS |
| TypeScript | PASS |
| Frontend tests | PASS — 47 tests in 7 files |
| Production frontend build | PASS |
| npm audit in the real frontend container | PASS — zero vulnerabilities |
| Compose base/test/demo configuration and builds | PASS |
| M0 Full Mode services/proxy/queue smoke | PASS |
| M1 upload/setup/validation smoke | PASS — all three classifiers and both weights, no automatic training |
| M2 training smoke | PASS — all 12 binary/multiclass/model/weight combinations |
| M3 Mode A smoke | PASS — binary and multiclass; frozen inference and unavailable labels |
| M4 Mode B smoke | PASS — binary/multiclass and absent-class cases; errors/privacy/immutable results |
| M5 slices/trends/reports/restart smoke | PASS — B–A–B gap, all signal groups, hashes, persistence and exact synthetic cleanup |
| M6 Demo smoke, before and after restart | PASS — 180 denied method/route pairs each time, safe GETs, no worker, unchanged counts/hashes |
| Browser, responsive, keyboard and print-preview checks | PASS — details below |
| Privacy/secret scan and complete diff review | PASS |
| Four locked specifications, original byte comparison | PASS |

## Docker / services / database / migrations

The isolated verification project is `modelmedic-m6-verified`, with API on localhost
18010 and frontend on localhost 15183. Full Mode verified PostgreSQL, API, frontend
and worker together, including worker heartbeat and restart persistence. Demo Mode
verified PostgreSQL/API/frontend with the worker stopped; worker health correctly
reports NOT_REQUIRED. The Demo API artifact volume is mounted read-only. No public
hosting, authentication expansion or deployment pipeline was introduced.

The existing explicit migration gate succeeded. Schema head remains `0006_m5`;
M6 adds no schema or migration. Scientific modules, domain validation, database
models, dependency locks and base Compose configuration remain unchanged.

## Demo Mode / Demo seed / Full Mode regression

Every non-GET API request is denied server-side with HTTP 403, including HEAD and
OPTIONS. Smoke enumeration derives all 30 API schema paths and tries six prohibited
methods through the real frontend proxy. Disabling Vite's independent CORS response
lets OPTIONS reach the API policy. Unknown GET routes are denied and nonregistered
resources return not found. Missing, corrupt, incompatible or changed seed scope
fails closed. Read requests never enqueue jobs or create missing reports.

The final PostgreSQL regression creates an unpublished draft through Full Mode on
an already seeded project. Demo history and readiness then return 503. Marking that
unpublished draft deletion-pending still returns 503: all run rows participate in
the scope comparison, regardless of state or cleanup status. Registered runs must
also remain analyzed and not deletion-pending. Full Mode mutation behavior continues
to pass every preceding lifecycle and scientific gate.

The deterministic generator uses seed 4200 + period, 1,500 baseline rows and 360
rows per current dataset, with generic synthetic fields. The existing completed
seed was created through actual upload, validation, training, establishment,
monitoring, slice and report pipelines. The final gate reverified generated source
SHA-256 values, stored output/report fingerprints, versions, established baseline
and B–A–B history. UUIDs and timestamps are naturally variable; synthetic source
bytes and same-version scientific outputs are reproducible. No fabricated results
or generated datasets/artifacts are committed.

Seed: Synthetic reliability lab, project `a1414e3b-b855-470a-be57-31e1ce04cc9b`.
Periods 1 and 3 have labels, stored slices and reports; Period 2 has no labels and
its performance history remains an explicit gap. Runtime provenance accurately
records the approved M5 SHA plus dirty source state for the precommit M6 candidate;
existing immutable artifacts are not relabeled to pretend they were built later.

## Browser verification / screen audit

Actual Full Mode browser work completed the entire baseline journey: create,
streamed upload, queued validation, profile/configuration, preprocessing review,
model/weight confirmation, explicit training, results, explicit establishment and
refresh persistence. It also completed actual Mode A and Mode B upload/validation,
explicit analysis, all analysis pages, separate slice analysis and saved results,
history, trends, report and methodology. Disposable browser fixtures were cleaned
by exact verified synthetic ownership; the seed remains available.

After the final gate, the real Demo browser recheck confirmed only the seeded
project, persistent READ-ONLY DEMO / Synthetic demo data, disabled direct project
and run forms, disabled slice analysis, stored baseline/Mode A/Mode B reads,
performance trends with a Mode A gap, and refresh persistence. Established
configuration routes display Baseline is locked. The six flagship screenshots
were captured from actual final seeded pages, without mock values.

| Screen | Audit result |
| --- | --- |
| S01 Projects | PASS — project table, scoped Demo list, disabled Demo creation |
| S02 Create Project | PASS — one prediction problem; Full journey and disabled Demo form |
| S03 Baseline Upload | PASS — real streamed upload and validation progress |
| S04 Dataset Profile | PASS — profile, warnings and explicit continuation |
| S05 Target & Features | PASS — target/positive class/features/types, frozen after establishment |
| S06 Preprocessing Review | PASS — deterministic review, no pre-training fitting |
| S07 Model & Weighting | PASS — three fixed classifiers and two weighting choices |
| S08 Confirmation / Training | PASS — explicit action, live stages and operational errors |
| S09 Baseline Results | PASS — all five sections, held-out vs CV distinction |
| S10 Establish Baseline | PASS — explicit review/action and persistent lock |
| S11 Project Overview | PASS — established four-section navigation |
| S12 Monitoring Runs | PASS — factual ordered history and scoped seed reads |
| S13 New Monitoring Run | PASS — real Full journey and disabled direct Demo form |
| S14 Analysis Progress | PASS — explicit analysis and actual worker stages |
| S15 Run Overview | PASS — independent signals and mode limitations |
| S16 Data | PASS — distribution/missingness/reliance views, Evidence Frame |
| S17 Feature Detail | PASS — observed distributions, missingness, range and reliance |
| S18 Predictions | PASS — frozen class order, shares and table alternative |
| S19 Confidence | PASS — probability range and descriptive mean/median |
| S20 Performance | PASS — held-out comparison, metrics and support |
| S21 Calibration | PASS — diagram, equal-size accessible points, bins and support |
| S22 Classes & Errors | PASS — neutral numbered matrices and bounded saved examples |
| S23 Slices | PASS — explicit separate Full analysis, persisted results, Demo disabled |
| S24 Mode A Unavailable | PASS — all four pages remain accessible with reasons |
| S25 Trends | PASS — one signal, factual order, B–A–B gap and no interpolation |
| S26 Reliability Report | PASS — stored evidence, limitations and monochrome preview |
| S27 Methodology & Glossary | PASS — actual navigation and keyboard anchor |
| S28 System/Error States | PASS — safe/next-action text, request ID, 404 and fail-closed runtime |

## Accessibility / responsiveness / print report verification

Actual desktop 1280, laptop 1024, tablet 768 and mobile 320 checks passed. At 320,
document client/scroll width both measured 305px (the scrollbar occupies the
remaining width). Wide analytical tables/charts scroll within their own containers;
limitations stay visible. Mobile feature tables precede plots. Run selection keeps
Mode A unavailable pages enabled. Menu keyboard activation and route focus passed;
the main content receives focus after navigation.

DOM inspection confirmed scoped table headers, sticky screen headers/identifiers,
numeric alignment, selective fonts, chart alternatives and focusable calibration
points exposing exact probabilities/frequencies/sample counts. Actual theme-token
contrast calculations exceeded 4.5:1 for text/status pairs and 3:1 for focus/control
borders/chart guides. Reduced-motion rules disable transitions/animations; no OS
screen-reader certification or unperformed native print check is claimed.

Mode A and Mode B print previews were inspected. Navigation/controls are hidden,
text is black, table headers are static, overflow is visible, maximum table height
is removed, wide-table alternatives are present and row splitting is avoided by
CSS. The same reviewed stylesheet serves preview and browser print. Native print
dialog and physical paper pagination remain the explicitly carried manual M7 check.

Ignored local screenshots: `.cache/m6-baseline.png`, `m6-mode-a.png`,
`m6-feature.png`, `m6-performance.png`, `m6-calibration.png`, `m6-trends.png`.
Additional real-browser training/mobile/print captures are also ignored.

## Privacy / security / locked specifications / scope

The Git candidate scan compared private local password/secret values without
printing them, checked common secret/token/private-key patterns and prohibited
dataset/artifact extensions. It found no credentials, `.env`, private data or
runtime artifacts among candidate files. Complete diff review and whitespace checks
passed. The four locked specifications match the original `8e2029a` bytes, not only
the approved M5 versions. No locked decision or previous Git history was altered.

No dark mode, health score, retrain/deploy controls, authentication scope expansion,
chatbot/LLM, scientific methodology changes or M7 functionality was implemented.

## Every original M6 requirement

| Requirement | Result |
| --- | --- |
| 1 Clinical Reliability Lab visual direction | PASS |
| 2 Inter UI and selective monospace statistics | PASS |
| 3 Semantic color tokens | PASS |
| 4 Four scientific status chips, text/icon/ARIA | PASS |
| 5 Locked global navigation | PASS |
| 6 Draft setup and established project navigation | PASS |
| 7 Run navigation and accessible Mode A unavailable pages | PASS |
| 8 Five-field Evidence Frame with backend interpretation | PASS |
| 9 Baseline/Current distinction without good/bad coloring | PASS |
| 10 Locked chart rules and table alternatives | PASS |
| 11 Analytical table conventions and no unsupported ranking | PASS |
| 12 S01–S28 conformance audit | PASS |
| 13 Desktop/laptop/tablet/mobile responsiveness | PASS |
| 14 Required accessibility checks | PASS |
| 15 Server-enforced seeded read-only Demo Mode | PASS |
| 16 Explicit mode, safe GET allowlist and non-GET enumeration | PASS |
| 17 Persistent Demo labels and exact disabled-action explanation | PASS |
| 18 Deterministic real-pipeline synthetic seed and versioning | PASS |
| 19 Worker-free Demo readiness; intact Full Mode services | PASS |
| 20 Six actual seeded flagship screenshots | PASS |
| 21 Actionable system/error states | PASS |
| 22 Monochrome print preview and CSS; native pagination carried as instructed | PASS |
| 23 Actual browser baseline/Mode A/Mode B and Demo journeys | PASS |
| 24 Frontend semantic/component regression tests | PASS |
| 25 Complete M0–M5 regression and unchanged stored science | PASS |
| 26 Quality/privacy/spec/diff/scope gates | PASS |
| 27 Genuine existing issues carried forward | PASS |
| 28 Exactly one milestone commit/push and Git verification | Completion report records actual publication evidence |
| 29 Structured report and stop before M7 | Completion report records final Git evidence; this record supplies acceptance detail |

## Known issues / Git / next

Carry forward: Starlette/httpx TestClient deprecation warning; inaccessible old
private artifact-prefix cleanup limitation; native print-dialog/physical-paper
pagination manual check. No new unresolved M6 acceptance failure remains.

Required single commit: `feat: complete ModelMedic user experience and demo mode`.
Required direct parent: `78f3a50b788d2ebd99fcd18be792c2d49b71978f`.
Verified configured identity: Manthan,
`156163069+manthan3502@users.noreply.github.com`.
The completion report verifies the actual commit, remote SHA and clean tree after
publication rather than placing a self-referential future SHA in this document.

NEXT: M7 — Hardening, Scientific QA, CI, Deployment. STOP BEFORE M7.
