# ModelMedic — Final UI/UX + Dashboard Blueprint

**Version:** 1.0  
**Status:** **LOCKED — STEP 7 COMPLETE**  
**Authoritative inputs:** ModelMedic Final PRD v1.0.1 + Technical Architecture Blueprint v1.0  
**Design basis:** Independent ChatGPT design pass + Claude UI/UX blueprint + Gemini visual/dashboard blueprint  
**Primary experience:** Desktop/laptop analytical application  
**Public deployment:** Read-only portfolio demo

---

# 1. Final Design Direction

ModelMedic should feel like a **scientific reliability workspace**, not an “AI product”.

The final visual concept is:

> **Clinical Reliability Lab**

The interface should communicate:

- precision
- skepticism
- analytical maturity
- reproducibility
- evidence
- calm confidence

It should **not** communicate:

- AI magic
- automated judgment
- urgency without evidence
- futuristic/cyberpunk aesthetics
- gamified “health”
- enterprise monitoring noise

The central visual idea is always:

> **Baseline vs Current**

Everything else stays visually quiet.

---

# 2. Final Three-Way Merge Decisions

## Kept primarily from Claude

- Evidence-frame pattern: **Measured → Result → Evidence → May conclude → Cannot conclude**
- state-driven routing
- guided baseline setup wizard
- explicit naming of **Held-out Baseline Reference** vs **All-row Drift Reference**
- full run-level navigation
- detailed validation/warning states
- Development CV visually separated from official held-out baseline
- full Feature Detail page
- methodology/glossary page
- Mode A analyses remain visible as **Unavailable**, never hidden
- deterministic report structure
- screen-by-screen scientific-risk guidance
- “signals, not verdicts” principle

## Kept primarily from Gemini

- calm light visual language
- subtle borders rather than heavy shadows
- baseline/current contrasting analytical colours
- dense but readable tables
- strong portfolio screenshot emphasis
- accessible text + icon + colour status system
- uncluttered data-first charts
- confusion-matrix and reliability-diagram visual emphasis
- no gauges, AI sparkles or decorative “insight” cards

## Final independent decisions

- **Light mode only in V1.** Dark mode is future scope.
- Mode A label-required pages use **Unavailable** iconography, not a padlock/“locked” metaphor.
- Confidence charts use a fixed **0–1 probability axis**. A subtle theoretical minimum `1/K` reference may be shown.
- Feature Detail is a **dedicated route/page**, not a modal or small drawer.
- Project Overview does **not** show three simultaneous sparklines. Detailed history belongs on the Trends screen.
- Reliability diagrams use normal points/lines; observation count is shown by labels/tooltips/bin table rather than relying on bubble size.
- Development CV uses a **five-point strip/dot plot + mean/SD**, not a box plot.
- Run History displays one selected analytical signal at a time.
- No global “settings” surface in V1; methodology and demo state are enough.
- No global project/run verdict of any kind.

---

# 3. UX Principles

## P1 — Answer five questions

Every analytical screen must make it possible to answer:

1. What changed?
2. How much changed?
3. What evidence supports it?
4. What may I conclude?
5. What may I **not** conclude?

## P2 — Signals, not verdicts

No page collapses evidence into:

- Overall health
- Reliability grade
- Needs attention
- Good / Bad
- Pass / Fail

## P3 — Labels gate claims

Label-dependent analyses remain visible in Mode A as:

> **Unavailable — ground-truth labels were not provided.**

They are not hidden.

## P4 — Evidence travels together

A statistical p-value is never shown alone.

Pair it with:

- test/statistic
- effect/distance information
- baseline n
- current n
- visual comparison
- interpretation limits

## P5 — Neutral direction

Change direction is not automatically good or bad.

Green is reserved for operational success such as:

- upload accepted
- training complete

Red is reserved for:

- blocking errors
- destructive/error states

`NOT DETECTED` is neutral, not green.

## P6 — “Cannot conclude” stays visible

Important scientific limitations are inline, not buried entirely in tooltips.

## P7 — Always name the baseline reference

Data drift / missingness:

> **Baseline: all valid baseline rows**

Model behaviour:

> **Baseline: held-out reference**

## P8 — Plain language first

Every statistical method gets:

- one plain-language explanation
- optional “How this is calculated” expansion

## P9 — Guardrails are guardrails

Whenever a sample-size rule is exposed:

> **Product guardrail — not a universal statistical law.**

## P10 — Progressive disclosure

Overview pages summarize.
Detail pages explain.

No single mega-dashboard.

## P11 — Honest charts

- no smoothing
- no forecasts
- no misleading truncated bounded axes by default
- no interpolation over missing history
- no 3D charts
- no decorative gauges

## P12 — Frontend is not a statistics engine

All:

- statuses
- calculations
- interpretation templates
- report wording

come from backend payloads.

The frontend only renders them.

---

# 4. Visual Design System

## 4.1 Theme

**Light mode only for V1.**

Reason:

- strongest readability for dense statistics
- print/report consistency
- less implementation/test complexity
- visually resembles a technical report/workbench

Future dark mode may be added later.

## 4.2 Typography

### UI / prose
`Inter`, with system sans-serif fallback.

### Numeric/statistical/code values
`JetBrains Mono`, with `ui-monospace` fallback.

Use monospace selectively for:

- p-values
- test statistics
- hashes
- versions
- methodology identifiers

Do not make entire tables monospace.

## 4.3 Colour roles

Suggested semantic tokens:

| Role | Direction |
|---|---|
| Page background | warm/off white |
| Surface/card | white |
| Main text | near-black/slate |
| Secondary text | slate gray |
| Border | light neutral gray |
| **Baseline** | muted indigo/navy |
| **Current** | teal/slate-teal |
| Detected | amber/orange |
| Not detected | neutral slate |
| Insufficient data | gray |
| Unavailable | gray |
| Blocking error | red |
| Operational success | green |

Colour is never the sole meaning carrier.

## 4.4 Surfaces

- 1 px neutral border
- subtle radius
- minimal shadow
- generous internal padding
- avoid floating glass cards
- avoid gradients except extremely subtle decorative header treatment, preferably none

## 4.5 Status chips

Every status chip includes:

- icon
- text
- accessible label

Statuses:

- `DETECTED`
- `NOT DETECTED`
- `INSUFFICIENT DATA`
- `UNAVAILABLE`

No severity chip.

## 4.6 Icons

Use restrained outline icons.

Do not use:

- sparkles
- robot icons
- magic wand
- lightning-bolt “AI insight”
- medical emergency symbolism

---

# 5. Information Architecture

```text
Application
├── Projects
│   └── Project
│       ├── Setup (DRAFT only)
│       ├── Baseline
│       ├── Monitoring Runs
│       │   └── Run
│       │       ├── Overview
│       │       ├── Data
│       │       ├── Predictions
│       │       ├── Confidence
│       │       ├── Performance        [Mode B]
│       │       ├── Calibration        [Mode B]
│       │       ├── Classes & Errors   [Mode B]
│       │       ├── Slices             [Mode B]
│       │       └── Report
│       └── Trends
└── Methodology & Glossary
```

---

# 6. Navigation

## Global top bar

Always visible.

Contains only:

- ModelMedic mark/name
- Projects
- Methodology
- Demo Mode badge when applicable

No:

- notification bell
- user avatar
- fake account menu
- global search
- settings page

## Breadcrumb

Example:

```text
Projects / Customer Churn / October 2026
```

## Project navigation

After baseline establishment:

```text
Overview | Baseline | Runs | Trends
```

During `DRAFT`, replace these with the setup stepper.

## Run navigation

Desktop left rail:

```text
Overview

WHAT CHANGED
  Data
  Predictions
  Confidence

NEEDS LABELS
  Performance
  Calibration
  Classes & errors
  Slices

Report
```

### Mode A

Label-dependent items remain visible and focusable as:

> **Unavailable**

Use a slashed-circle/info icon, not a padlock.

Selecting one opens the explanatory unavailable screen.

### Mode B

All sections active.

---

# 7. Baseline Setup Stepper

Desktop: left vertical stepper.

```text
DATA
1. Upload
2. Review data

CONFIGURE
3. Target & features
4. Preprocessing
5. Model

TRAIN
6. Confirm & train
7. Baseline results

LOCK
8. Establish baseline
```

States:

- Complete
- Current
- Not started
- Needs attention

Text labels accompany all icons.

Users may revisit previous steps while project state is `DRAFT`.

Changing a dependency after training requires confirmation that draft training results will be discarded.

---

# 8. Screen Inventory

| ID | Screen |
|---|---|
| S01 | Projects |
| S02 | Create Project |
| S03 | Baseline Upload |
| S04 | Dataset Profile |
| S05 | Target & Features |
| S06 | Preprocessing Review |
| S07 | Model & Weighting |
| S08 | Confirm / Training Progress |
| S09 | Baseline Results |
| S10 | Establish Baseline |
| S11 | Project Overview |
| S12 | Monitoring Runs |
| S13 | New Monitoring Run |
| S14 | Analysis Progress |
| S15 | Run Overview |
| S16 | Data Drift |
| S17 | Feature Detail |
| S18 | Predictions |
| S19 | Confidence |
| S20 | Performance |
| S21 | Calibration |
| S22 | Classes & Errors |
| S23 | Slices |
| S24 | Mode A Unavailable Explainer |
| S25 | Trends |
| S26 | Reliability Report |
| S27 | Methodology & Glossary |
| S28 | System/Error States |

---

# 9. S01 — Projects

## Purpose

Entry point for project lifecycle.

## Layout

Full-width list/table, not a card grid.

Columns:

- project name + description
- state
- model
- target
- baseline-established date
- run count
- last activity

Optional small run markers indicate:

- run order
- Mode A / Mode B shape only

They never indicate “good/bad”.

## Primary action

**New project**

## Empty state

> No projects yet. A project holds one baseline model and every newer dataset you compare against it.

Three short steps:

1. Establish a baseline
2. Check newer data
3. Read the evidence

## Demo

Seeded projects show:

> Synthetic demo data

New Project stays visible but disabled with:

> Uploading and mutation are disabled in the public demo.

---

# 10. S02 — Create Project

Fields:

- Name
- Description (optional)

Side explainer:

> A ModelMedic project is one prediction problem: one target, one frozen baseline model and every later dataset compared against it.

Do not ask about:

- drift thresholds
- preprocessing configuration
- statistical tests

Primary:

**Create project and upload baseline**

---

# 11. S03 — Baseline Upload

Centered workflow.

Components:

- drag/drop
- file selector
- privacy notice
- upload details

## Upload phase

Real byte progress is allowed.

## Validation phase

Stage text only:

- Reading file
- Checking columns
- Building typed copy

No fake percent.

## Accepted

Operational success state.

## Rejected

Blocking red panel listing every reason and resolution.

Never call guardrail rejection “corruption”.

---

# 12. S04 — Dataset Profile

## Summary

- rows
- columns
- duplicates
- inferred numeric features
- inferred categorical features

## Warnings

Show before the full table.

Examples:

- likely identifier
- constant
- high missingness
- ≤10 distinct numeric values
- categorical cardinality
- datetime/free-text unsupported
- whitespace-differing categories
- numeric-looking column containing literal `NA`/`N/A`

## Column table

Columns:

- feature
- inferred type
- missing %
- distinct count
- sample values
- flags
- target eligibility

Preview first 10 rows as escaped text.

Copy:

> ModelMedic does not silently clean or delete your data. It shows what it found so you can decide what belongs in the model.

---

# 13. S05 — Target & Features

## Target section

After target selection show:

- classes
- counts
- proportions

Binary:

require explicit positive class.

Copy:

> Which outcome are you trying to catch? Precision, recall, F1 and false positives/negatives use this class as the event of interest.

## Feature table

- Include
- Feature
- Type
- Flags
- Recommendation / reason

Allow Numeric ↔ Categorical override only where valid.

Unsupported features are read-only excluded.

Sticky summary:

```text
17 included
9 numeric
8 categorical
~312 encoded columns / 2,000 computational limit
```

Do not recommend a target.

---

# 14. S06 — Preprocessing Review

Use one simple pipeline:

```text
Raw columns
    ↓
Handle missing values
    ↓
Encode categories
    ↓
Scale numeric values when required
    ↓
Classifier
```

Explain:

### Median imputation
All classifiers.

### Explicit missing category
All classifiers for categoricals.

### One-hot encoding
All classifiers.

### StandardScaler
Logistic Regression only.

Two important callouts:

> Learned from the Development 80% only.

> Frozen after baseline establishment.

No editable switches.

---

# 15. S07 — Model & Weighting

Three equal options:

### Logistic Regression
Simple probabilistic linear model.

### Random Forest
Non-linear ensemble of trees.

### Gradient Boosting
Sequential boosted trees.

Each contains:

- plain-language description
- one trade-off sentence

No:

- Recommended
- Best
- Winner
- score prediction

Weighting:

- Standard
- Balanced

Show class proportions nearby.

Primary:

**Review and train**

---

# 16. S08 — Confirm & Train

Pre-training summary:

- target
- positive class
- features/types
- model
- weighting
- 80/20 split
- 5-fold CV
- seed 42
- held-out per-class guardrail

## Training stage tracker

```text
Checking data
Splitting data
Running 5-fold CV
Fitting final model
Evaluating held-out reference
Checking calibration
Measuring feature reliance
Saving baseline
Done
```

Use:

- current-stage activity indicator
- completed-stage check
- elapsed time

Never:

- fake %
- fake ETA
- tentative live metrics

Failures include actionable, sanitized explanations.

---

# 17. S09 — Baseline Results

This is one of the flagship portfolio screens.

Tabs:

```text
Summary
Performance
Calibration
Model reliance
Data reference
```

## Permanent reference ribbon

Primary:

> **Official baseline = Held-out Baseline Reference**

Secondary:

> **Development CV = diagnostics only**

These two visual roles must never look interchangeable.

## Summary

- model/configuration
- split sizes
- per-class held-out support
- important warnings
- baseline metrics

## Performance

### Held-out Reference
Primary section.

Metrics table + class metrics + confusion matrix.

### Development CV
Separate diagnostic section.

For each selected metric:

- five fold dots
- mean
- SD
- min–max

No box plot; there are only five folds.

## Calibration

Baseline reliability diagram.

## Model reliance

Horizontal dot-and-whisker:

- mean permutation importance
- ± SD
- zero line
- negatives preserved

## Data reference

- frozen features/types
- class counts
- missingness
- baseline references
- reproducibility info

---

# 18. S10 — Establish Baseline

Calm final confirmation.

Two lists.

## This becomes frozen

- model
- preprocessing
- features/types
- target / positive class
- baseline reference

## You can still do

- create monitoring runs
- inspect history
- generate reports

Primary:

**Establish baseline**

Copy:

> Locking keeps later comparisons fair because every new run is evaluated against the same model, preprocessing and reference.

No typed destructive confirmation.

---

# 19. S11 — Project Overview

Do **not** create a health dashboard.

Show:

## Project facts

- model
- target
- positive class
- weighting
- baseline size
- methodology version

## Held-out baseline reference

Compact factual metric table.

## Recent runs

Latest five.

## Primary action

**New monitoring run**

## History preview

Do not show three simultaneous sparklines.

Use one understated panel:

> Monitoring history is available in Trends.

Optionally show the last three run markers and link to Trends.

This keeps the landing page from implying an overall trajectory.

---

# 20. S12 — Monitoring Runs

Table:

- Run
- Monitoring date
- Mode
- Rows
- State
- Features with detected distribution change (`x of y tested`)
- Median confidence
- Balanced Accuracy (Mode B)
- F1/Macro F1 (Mode B)
- Warning count

Mode A metric cells say:

> No labels

Never blank and never zero.

Counts of detected tests are factual counts, not severity.

---

# 21. S13 — New Monitoring Run

Single-page three-step flow:

## 1. Details

- Run name
- Monitoring date
- Notes

## 2. Upload

Same safe upload pattern as baseline.

## 3. Review before analysis

Show:

- required features present
- extra columns
- coercions
- row count
- validation warnings

Then one large mode block:

### Mode A — Labels unavailable

or

### Mode B — Labels available

Show matrix:

| Analysis | A | B |
|---|---|---|
| Data / missingness | Included | Included |
| Predictions | Included | Included |
| Confidence | Included | Included |
| Performance | Unavailable | Included |
| Calibration | Unavailable | Included |
| Errors/classes | Unavailable | Included |
| Slices | Unavailable | Available after analysis |

Frozen-model statement:

> The established model and preprocessing are applied exactly as frozen. Nothing is retrained, refitted or updated from this file.

---

# 22. S14 — Monitoring Analysis Progress

Stages:

```text
Checking data
Running predictions
Analyzing data distributions
Analyzing missingness
Analyzing prediction distribution
Analyzing confidence
Measuring performance       [Mode B]
Analyzing calibration       [Mode B]
Saving results
Done
```

No percent.

No partial results become visible before atomic finalization.

---

# 23. S15 — Run Overview

This is the second flagship screen.

## Persistent mode banner

### Mode A

> **Labels unavailable. Actual current predictive performance and calibration cannot be measured.**

Explain:

> Data, prediction and confidence changes are warning signals. They do not show whether predictions became less accurate.

### Mode B

> **Labels provided. Actual performance and calibration were measured.**

No success-style colouring.

## Question group 1 — What changed in the data?

Cards:

- Distribution changes
- Missingness
- Categories / ranges

## Question group 2 — Did model behaviour change?

Cards:

- Prediction distribution
- Confidence

## Question group 3 — Did measured performance change?

Mode B:

- Performance
- Calibration

Mode A:

one Unavailable panel listing every label-dependent analysis and why it was not measured.

No overall status.

No severity ranking.

No “needs attention” count.

---

# 24. Common Evidence Frame

Every analysis-detail screen begins with a consistent evidence block:

### Measured
What quantity is being compared.

### Result
The factual result.

### Evidence
Statistic, distance/effect, sample sizes, adjusted p-value where applicable.

### May conclude
What the result supports.

### Cannot conclude
The most important limitation.

The visual structure stays identical across Data, Predictions, Confidence, Performance and Calibration.

---

# 25. S16 — Data Drift

Tabs:

```text
Distribution
Missingness
Reliance × change
```

## Summary

- tested features
- Detected
- Not detected
- Insufficient data
- BH family size

## Distribution table

Filters:

- Type
- Status
- New categories
- Caution flags
- Feature search

Default grouping:

1. Detected
2. Not detected
3. Insufficient

Within detected:
- Numeric and Categorical are separate groups.
- Sort only within a scientifically comparable type.

Never create a “Top drifting features” ranking.

## Missingness

Sort by absolute percentage-point change.

## Reliance × change

Sort by baseline permutation reliance, not a combined score.

---

# 26. S17 — Feature Detail

**Dedicated full page.**

Do not use a small modal.

## Header

- feature
- type
- distribution status
- missingness status
- relevant caution flags

## Primary chart

Numeric:
- baseline/current normalized histogram or step histogram

Categorical:
- paired horizontal baseline/current bars

## Evidence panel

- test
- statistic
- raw p
- adjusted p
- family size
- baseline n
- current n
- Wasserstein / JS
- categorical pooling notes where applicable

## Additional cards

- missingness
- category/range change
- baseline model reliance
- interpretation

Always include:

> ModelMedic does not claim this feature change caused any change in performance.

---

# 27. S18 — Predictions

Purpose:

> Did the model output different classes more often?

## Chart

For each frozen class, use paired horizontal bars:

```text
Baseline  ███████
Current   ██████████
```

This is easier to compare than a single stacked bar for up to 10 classes.

Keep frozen class order.

## Table

- Class
- Baseline share
- Current share
- Δ pp
- Baseline count
- Current count

## Evidence

- JS distance
- test
- p
- baseline n
- current n
- status

Explicit:

> Prediction shift does not tell you whether the predictions are correct.

---

# 28. S19 — Confidence

## Chart

Normalized baseline/current histogram.

**Fixed x-axis: 0 to 1.**

Show a faint reference marker at:

```text
1 / number_of_classes
```

if useful.

Median markers:

- Baseline
- Current

Stats:

- mean
- median
- KS D
- p
- baseline n
- current n

Copy:

> Lower confidence does not by itself mean lower accuracy.

---

# 29. S20 — Performance (Mode B)

Always start with:

> Small metric differences may reflect sampling variation. V1 does not estimate confidence intervals for performance changes.

## Class mix

Baseline held-out vs current true-label proportions.

Any absent baseline class triggers a visible comparability warning.

## Overall metric table

Group:

### Classification performance
- Accuracy
- Balanced Accuracy
- Precision / Recall / F1 as appropriate

### Ranking
- ROC-AUC
- Average Precision

### Probability quality
- Log Loss
- Brier

Columns:

- Metric
- Baseline
- Current
- Δ
- Baseline support
- Current support
- Availability / note

No red/green deltas.

## Visual comparison

Use compact dumbbell/dot comparison for bounded metrics.

Fixed 0–1 axis where mathematically bounded.

## Per-class table

- Precision
- Recall
- F1
- Support

No “best/worst class”.

---

# 30. S21 — Calibration (Mode B)

## Explainer

> When the model predicts a probability, how closely does that probability match what actually happened?

## Reliability chart

- x = mean predicted probability
- y = observed frequency
- reference diagonal
- Baseline line/points
- Current line/points

Use consistent point size.

Do **not** make point size the primary support encoding.

Support is shown through:

- tooltip
- direct bin count on focus/hover
- bin table below

## Metrics

- Brier Score — “probabilistic prediction quality”
- Log Loss

## Multiclass

Class selector for One-vs-Rest.

## Warnings

n < 250:

> Limited-support calibration estimate.

Insufficient positive/non-positive:

> Unavailable — insufficient support.

No “well calibrated” verdict chip.

---

# 31. S22 — Classes & Errors

## Binary

- baseline confusion matrix
- current confusion matrix
- normalized rate default
- count toggle

Below:

- False Positives
- False Negatives

Up to 50 example rows.

## Multiclass

- normalized confusion matrix
- baseline/current switch or side-by-side on wide screens
- common confusion-pairs list

Use one-hue sequential matrix.

Do not use “error = red”.

---

# 32. S23 — Slices

Persistent message:

> Slice comparisons are exploratory. No statistical significance testing or multiplicity correction is performed across slices. This is not a fairness audit.

User selects one eligible categorical model feature.

Results:

- All rows reference
- Slice
- n
- class support
- metric set

Below n=30:

> Insufficient sample size for stable slice analysis.

Optional dot plot for one metric with overall reference line.

Never:

- sort by worst by default
- label a worst slice
- use bias/parity/fairness terminology

---

# 33. S24 — Mode A Unavailable

Used when a user opens:

- Performance
- Calibration
- Classes & Errors
- Slices

Show:

## Why unavailable

> This run did not include ground-truth labels.

## What you can still inspect

- Data
- Predictions
- Confidence

## How to measure it

> Create a new monitoring run from a dataset that includes complete valid labels.

Do not use disabled fake charts.

---

# 34. S25 — Trends

The Trends screen shows **one selected signal at a time**.

Control:

1. Signal group
2. Signal
3. Feature/class selector if needed

Signals include:

- Balanced Accuracy
- F1 / Macro F1
- Precision/Recall
- Brier
- Log Loss
- Median confidence
- Mean confidence
- Predicted class share
- KS statistic
- JS distance
- Missingness %

## Chart

- baseline/reference point if meaningful
- monitoring runs ordered by Monitoring Date
- marker shape differentiates Mode A/B
- no interpolation across missing labeled metrics
- no forecast
- no regression line
- no “bad zone”

Below:

factual table with:

- run
- date
- mode
- value
- n
- status / adjusted p where relevant

---

# 35. S26 — Reliability Report

Print-friendly single-column document.

Sections:

1. Project
2. Baseline
3. Run
4. Schema/compatibility
5. Data changes
6. Prediction behaviour
7. Confidence
8. Performance or unavailable reason
9. Calibration or unavailable reason
10. Classes & errors
11. Slices if created
12. Limitations

Each key finding follows:

```text
Measured
Result
Evidence
May conclude
Cannot conclude
```

Footer:

> Generated from stored results using fixed reviewed templates. No language model generated this report.

Print:

- hide navigation
- direct chart labels
- table alternative
- avoid table split where practical
- preserve monochrome readability

---

# 36. S27 — Methodology & Glossary

Static learning/reference page.

Sections:

- baseline split
- cross-validation
- preprocessing
- metrics
- KS
- Wasserstein
- Jensen-Shannon
- chi-square
- Fisher exact
- BH/FDR
- confidence
- calibration
- permutation importance
- slices
- guardrails
- limitations

Searchable glossary.

This screen is valuable in interviews and should match locked methodology exactly.

---

# 37. S28 — System/Error States

Standardized screens/panels for:

- 404
- API unavailable
- generic server error + request ID
- read-only demo action
- artifact compatibility error
- job interrupted
- validation failed
- run not ready
- deletion in progress

Error language must explain:

1. What happened
2. What remains safe
3. What the user can do next

---

# 38. Data Visualization System

## Numeric feature distribution

**Normalized step histogram**

- baseline = muted indigo
- current = teal
- identical bin edges
- n displayed

Avoid KDE by default; bandwidth can invent apparent structure.

## Categorical feature distribution

**Paired horizontal bars**

- frozen/category display order
- baseline/current share
- show new/disappeared markers as text/icon

## Prediction distribution

**Paired horizontal bars per class**

rather than relying only on a 100% stacked bar.

## Confidence

Normalized histogram, 0–1 x-axis.

## Calibration

Reliability diagram + diagonal + bin table.

## Permutation importance

Horizontal dot-and-whisker:
- mean
- SD
- zero line
- negatives preserved

## Confusion matrix

Single-hue sequential heatmap with direct numbers.

## CV diagnostics

Five-point strip plot + mean/SD.

## Performance comparison

Table first.
Optional dumbbell for selected bounded metrics.

## Trends

One signal.
No forecast/interpolation.

---

# 39. Table System

Analytical tables are first-class, not secondary to charts.

Defaults:

- sticky header for long tables
- feature/run name sticky on horizontal scroll
- compact but not cramped row height
- numeric values right aligned
- status left aligned
- monospace only for technical/statistical columns

Every chart should have either:

- an adjacent table
- or “View as table”

Sorting restrictions must match scientific meaning.

Examples:

- no cross-type Wasserstein ranking
- no “worst slice” default
- no project/run severity sort

---

# 40. Status and Warning System

## DETECTED

Amber outline/fill accent + warning/evidence icon.

Meaning:

> statistical evidence of difference

Not:

> bad / severe

## NOT DETECTED

Neutral slate + outlined circle/check-style evidence icon.

Never green.

## INSUFFICIENT DATA

Gray + incomplete/dashed icon.

## UNAVAILABLE

Gray + slashed-circle/info icon.

## BLOCKING ERROR

Red.

## OPERATION SUCCEEDED

Green.

---

# 41. Mode A / Mode B Visual Language

Mode chips:

### Mode A
Neutral gray/slate.

Label:

> **Mode A — labels unavailable**

### Mode B
Muted blue/indigo.

Label:

> **Mode B — labels available**

Do not make Mode B look “healthier” or better.

The difference is **information availability**, not quality.

---

# 42. Responsive Behaviour

## Desktop ≥1280

Full analytical layout.

## Laptop 1024–1279

Same IA, narrower cards/tables.

## Tablet 768–1023

- project horizontal tabs remain
- run sidebar collapses to section menu
- charts stack
- tables horizontally scroll
- sticky first column

## Mobile <768

Mobile is a review experience, not the primary analysis workspace.

- single column
- collapsed navigation
- summary cards
- “View table” prioritized
- dense matrices/tables scroll horizontally
- Feature Detail content stacks
- no attempt to compress every desktop chart into tiny cards

Do not hide scientific limitations on mobile.

---

# 43. Accessibility

Minimum requirements:

- WCAG AA text contrast
- keyboard reachable navigation
- visible focus state
- semantic heading order
- table headers correctly associated
- status meaning present in text
- tooltips accessible on focus, not hover-only
- chart table alternatives
- matrix values directly readable
- live regions for job stage updates
- no information conveyed only through colour
- reduced-motion preference respected

---

# 44. Public Demo Mode

Permanent top-bar badge:

> **READ-ONLY DEMO**

Seeded projects:

> Synthetic demo data

Mutation controls may remain visible but disabled where educationally useful.

Tooltip/inline explanation:

> This action is disabled in the public portfolio demo. Run ModelMedic locally to upload your own data.

Do not fake upload/training interactions.

---

# 45. Portfolio Screenshot Priorities

The strongest 6 screenshots:

## 1. Baseline Results
Shows held-out discipline + model reliance.

## 2. Mode A Run Overview
Shows scientific restraint when labels are missing.

## 3. Data Drift + Feature Detail
Shows BH-corrected statistical monitoring.

## 4. Mode B Performance
Shows baseline/current comparisons and support.

## 5. Calibration
Shows probability reliability with limitations.

## 6. Trends
Shows multiple monitoring runs and gaps for unlabeled performance.

README should explain **why** each screenshot matters rather than merely captioning UI.

---

# 46. UX Copy Rules

Prefer:

> Statistical evidence of a distribution difference was detected.

Avoid:

> Severe drift found!

Prefer:

> No evidence of a difference was detected in these samples.

Avoid:

> Data is stable.

Prefer:

> Performance cannot be measured because this run has no labels.

Avoid:

> Performance locked.

Prefer:

> This feature deserves investigation.

Avoid:

> This feature caused the model to degrade.

Prefer:

> Investigation is recommended.

Avoid:

> Retrain now.

---

# 47. What Must Never Be Added to the UI

- Model Health score
- Trust score
- Risk score
- overall red/yellow/green result
- retrain action
- deploy action
- chatbot
- AI insight button
- sparkle icons
- SHAP dashboard
- AutoML model comparison
- streaming controls
- notification center
- alert configuration
- model registry UI
- fairness verdict
- “worst slice”
- “top drifting feature” leaderboard
- predictive trend/forecast
- fake loading percentages

---

# 48. Implementation Waves

## Wave 1 — Design foundation

- app shell
- typography
- tokens
- status chips
- tables
- Evidence Frame
- empty/error/loading states
- Demo Mode system
- chart wrappers and table alternatives

## Wave 2 — Baseline setup

S01–S10.

The full baseline flow must work before monitoring UI.

## Wave 3 — Mode A monitoring

S11–S19 plus Mode A unavailable states.

This proves drift, prediction and confidence UX without labels.

## Wave 4 — Mode B

Performance, calibration, errors, classes, slices.

## Wave 5 — History and presentation

- Trends
- Reliability Report
- Methodology / Glossary
- final responsive/accessibility polish
- portfolio screenshot pass

---

# 49. UX Acceptance Criteria

The UI/UX is accepted only if:

1. A new user can explain what a ModelMedic project is from S02.
2. The baseline wizard visibly separates development CV from held-out baseline.
3. The user sees the frozen-pipeline consequence before Establish Baseline.
4. Mode A cannot visually imply measured performance degradation.
5. Mode A label-dependent areas remain visible as Unavailable.
6. Mode B adds performance/calibration without changing the meaning of Mode A signals.
7. Every drift p-value appears with supporting evidence/sample sizes.
8. Distribution and missingness statuses remain separate.
9. Data drift uses the all-row baseline label; model behaviour uses the held-out label.
10. No page displays a global model-health verdict.
11. No red/green colouring implies metric quality.
12. Calibration always exposes support/bin counts.
13. Negative permutation importance is visually retained.
14. Slice analysis visibly states that it is exploratory.
15. Trends do not interpolate unlabeled performance.
16. Unavailable values never appear as zero.
17. Demo Mode cannot appear writable.
18. All important charts have a table/text alternative.
19. Keyboard users can reach all actions/status explanations.
20. The report remains understandable when printed without colour.
21. The interface never exposes a retrain/deploy/AutoML workflow.
22. The frontend never calculates scientific statistics.
23. Mobile preserves scientific limitations even when charts simplify.
24. The six flagship screens are screenshot-ready for README/portfolio use.

---

# 50. Final UI/UX Lock

The following decisions are now locked for V1:

- Clinical Reliability Lab visual direction
- light mode only
- Baseline vs Current as the primary comparison language
- Inter-style UI typography + monospace for statistics
- project horizontal navigation + run-side navigation
- guided baseline setup
- Development CV / Held-out Reference strict visual separation
- persistent Mode A / Mode B context
- Unavailable, not hidden, label-dependent analyses
- no lock/padlock metaphor for missing labels
- Evidence Frame on analytical detail pages
- full-page Feature Detail
- normalized raw-distribution visuals
- paired class bars for predictions
- confidence axis fixed to 0–1
- table-first performance comparison
- standard reliability diagram + explicit bin counts
- negative permutation importance preserved
- exploratory slice language
- one-signal-at-a-time Trends
- deterministic printable report
- static methodology/glossary
- no health score/severity/retrain/deploy/AI assistant
- accessible status system not dependent on colour
- desktop-first with honest mobile degradation
- read-only public demo presentation

---

# Status

## **STEP 7 — MODEL MEDIC UI/UX + DASHBOARD BLUEPRINT: LOCKED**

This document is the authoritative V1 UI/UX specification.

Frontend implementation should conform to this document, the locked PRD and the locked Technical Architecture Blueprint.

The next project-planning stage is:

> **STEP 8 — Milestone-by-Milestone Implementation Plan**

No frontend or backend implementation should silently alter locked scientific, architecture or UX decisions.
