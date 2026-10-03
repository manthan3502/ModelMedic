# ModelMedic — ML Reliability & Drift Analysis Platform

## Final V1.0 Product Requirements Document

**Version:** 1.0.1  
**Status:** **LOCKED**  
**Product type:** Full-stack batch ML reliability and drift-analysis platform  
**ML domain:** Classical tabular classification  
**Portfolio direction:** Applied AI / Full-Stack AI Engineering  
**Architecture:** Defined separately after PRD lock

---

# 1. Executive Summary

ModelMedic is a full-stack ML reliability platform for tabular classification models.

Its central question is:

> **“My ML model worked well before. Can I still trust it on newer data?”**

The user establishes a reproducible classification baseline from historical labeled CSV data. ModelMedic validates the dataset, fits reproducible preprocessing and one supported classifier, evaluates the final pipeline on untouched held-out reference data, and freezes the baseline.

Later datasets are uploaded as monitoring runs.

ModelMedic compares current behaviour with the baseline and reports separate evidence about:

- schema/data quality
- feature drift
- missingness
- category/range changes
- prediction-distribution changes
- prediction-confidence changes
- actual predictive performance when labels exist
- calibration when labels exist
- errors/classes/slices
- feature diagnostics
- historical trends

ModelMedic deliberately avoids composite “Model Health Scores”, causal claims, and automatic retraining instructions.

---

# 2. Core Scientific Principle

ModelMedic reports **evidence, not manufactured certainty**.

It must always distinguish:

1. data changed
2. predictions changed
3. confidence changed
4. actual performance changed

The fourth statement requires current ground-truth labels.

Data drift by itself does **not** prove model degradation.

---

# 3. Product Goals

- establish a reproducible leakage-free baseline
- measure later data change
- measure later prediction/confidence change
- measure actual performance only when labels exist
- evaluate calibration only when labels exist
- expose class/error/slice/feature diagnostics
- preserve monitoring history
- create deterministic evidence-based reports
- remain explainable to a final-year CSE student
- demonstrate classical ML + statistics + full-stack engineering

---

# 4. Non-Goals

V1 is not:

- AutoML
- enterprise MLOps
- a model registry
- model serving/deployment
- automated retraining
- scheduled/streaming monitoring
- Kafka/Kubernetes
- distributed training
- deep learning
- NLP/image monitoring
- regression
- forecasting
- RAG/chatbot/LLM monitoring
- SHAP-heavy explainability
- fairness/protected-attribute auditing
- anomaly-detection platform
- MLflow/experiment-tracking clone
- composite model-health scoring

---

# 5. Key Entities

## Project
One prediction problem consisting of one frozen baseline dataset, one target, one feature schema, one fitted preprocessing pipeline, one trained classifier and zero or more monitoring runs.

## Development Set
Stratified 80% of baseline data used for fitting and 5-fold stratified CV diagnostics.

## Held-out Baseline Reference
Stratified 20% untouched during fitting. Official model-behaviour reference for metrics, predictions, confidence, calibration and permutation importance.

## Drift Reference Data
All valid raw baseline rows used for feature-distribution and missingness comparisons.

## Monitoring Run
One current dataset analyzed against the frozen baseline.

## Mode A
Current labels unavailable.

## Mode B
Current labels completely available and valid.

## Confidence
Maximum predicted class probability.

## Guardrail
A transparent V1 product rule, not a universal statistical law.

## Model Reliance
Permutation importance. It is not causal importance.

---

# 6. Supported Data and Tasks

Supported:

- CSV
- tabular features
- binary classification
- multiclass classification
- scikit-learn classifiers
- small-to-medium in-memory datasets

Unsupported:

- images
- raw-text modelling
- NLP
- deep learning
- regression
- time-series forecasting
- multilabel targets
- arbitrary uploaded model binaries

---

# 7. Supported Classifiers

Exactly:

1. Logistic Regression
2. Random Forest
3. Gradient Boosting Classifier

The user selects one.

No automatic model winner.
No AutoML.
No automated hyperparameter search.

---

# 8. Feature Types

Supported modelling feature types:

- Numeric
- Categorical

Categorical feature maximum cardinality:

**100 distinct categories**

Unsupported modelling types:

- raw datetime
- free text
- categoricals above the cardinality guardrail

---

# 9. Feature-Type Review

ModelMedic infers feature types during baseline setup.

The user may override numeric ↔ categorical where both interpretations are reasonable.

If an integer/numeric feature has **10 or fewer distinct non-missing values**, display:

> Review feature type — this feature may represent categories.

If the user keeps such a tied/discrete feature numeric, the later KS p-value must carry a caution that the continuous-distribution assumption is imperfect.

Final baseline feature types are frozen.

Current uploads never re-infer feature semantic types.

---

# 10. Target Requirements

Binary:

- exactly 2 classes
- user explicitly selects positive/event class

Multiclass:

- 3–10 classes

Baseline target must contain no missing labels.

Unsupported:

- one-class target
- continuous target
- >10 classes
- multilabel target

---

# 11. Baseline Sample Guardrails

Effective minimum usable baseline rows:

> **max(200, 100 × number_of_target_classes)**

Pre-split requirements:

- at least 100 observations per target class

After actual stratified 80/20 split:

- each target class must have at least 20 observations in the Held-out Baseline Reference

The post-split held-out check is authoritative.

If any requirement fails:

> baseline establishment is blocked.

If any held-out class has only **20–29 observations**, show a low-support warning for class-level metrics, calibration and permutation-importance interpretation.

These are ModelMedic V1 guardrails, not universal statistical sufficiency claims.

---

# 12. Baseline Validation

Blocking:

- unreadable CSV
- empty dataset
- missing header
- duplicate column names
- baseline below sample guardrails
- invalid target
- unsupported included feature
- categorical cardinality above limit

Warnings:

- duplicates
- constant columns
- high missingness
- potential IDs
- strong class imbalance
- low-cardinality numeric feature-type warning

ModelMedic does not silently delete rows.

---

# 13. Missing-Value Parsing

Baseline and current datasets use one documented, consistent missing-value parsing policy.

Missingness must be visible to the user before baseline establishment.

Exact parser/token implementation is an engineering detail, but it must be identical between baseline and current runs.

---

# 14. Target Normalization

Target labels are normalized consistently.

Safe whitespace trimming is allowed.

Normalization must not silently merge genuinely different classes.

---

# 15. Feature Selection

For each non-target column:

- Include
- Exclude

Potential ID/high-cardinality columns are flagged with a recommendation.

No silent exclusion.

---

# 16. Preprocessing

Missing-value handling applies to **all three classifiers**.

## Numeric
All models:
- median imputation

Logistic Regression only:
- StandardScaler after imputation

Random Forest:
- median imputation
- no StandardScaler

Gradient Boosting:
- median imputation
- no StandardScaler

## Categorical
All models:
- explicit missing-category handling
- One-Hot Encoding
- unknown future categories do not crash inference

Unknown categories must still be reported as monitoring changes.

---

# 17. Leakage Prevention

Preprocessing and classifier fitting use the Development Set only.

Held-out data must not affect:

- imputation medians
- scaler parameters
- encoder categories
- classifier fitting

Monitoring data must never:

- refit preprocessing
- retrain classifier
- update encoder categories
- update scaler statistics

---

# 18. Baseline Split

Use:

- 80% Development Set
- 20% Held-out Baseline Reference
- stratified split
- random seed 42

Actual post-split per-class held-out counts must satisfy Section 11.

---

# 19. Development Cross-Validation

Within the Development Set use:

**5-fold Stratified Cross-Validation**

Purpose:

- diagnostic stability only

Not:

- automated model selection
- hyperparameter optimization

---

# 20. Class Imbalance

Always show class counts and percentages.

User chooses:

- Standard weighting
- Balanced weighting

No SMOTE.
No automated over/undersampling.

No universal imbalance threshold is claimed.

---

# 21. Baseline Workflow

1. Create Project
2. Upload Baseline CSV
3. Validate
4. Preview dataset
5. Select target
6. Select binary positive class if needed
7. Review feature types
8. Include/exclude features
9. Review data profile/warnings
10. Review preprocessing
11. Select classifier
12. Select Standard/Balanced weighting
13. Confirm configuration
14. Train
15. Review 5-fold development diagnostics
16. Review held-out baseline evaluation
17. Establish Baseline

After establishment, baseline configuration is immutable.

---

# 22. Binary Metrics

For labeled evaluation:

- Accuracy
- Balanced Accuracy
- Precision
- Recall
- F1
- ROC-AUC where valid
- Average Precision where valid
- Log Loss
- Brier Score
- Confusion Matrix
- support

Accuracy is never shown alone.

---

# 23. Multiclass Metrics

- Accuracy
- Balanced Accuracy
- Macro Precision
- Macro Recall
- Macro F1
- Weighted F1
- per-class Precision/Recall/F1/Support
- Macro ROC-AUC One-vs-Rest where valid
- Log Loss
- multiclass Brier formulation
- Confusion Matrix

Undefined metrics display:

> Unavailable + reason

Never fake zero.

---

# 24. Frozen Probability Class Order

The baseline target-class list and probability-column order are frozen with the model.

All probability-based calculations must use that frozen order:

- predict_proba mapping
- Log Loss
- Brier
- ROC-AUC
- calibration

Current datasets must never redefine class order.

---

# 25. Monitoring Runs

Each run requires:

- Run Name
- Monitoring Date

Optional:

- notes

Creation timestamp is stored separately.

History ordering:

1. Monitoring Date
2. Creation Timestamp
3. internal Run ID

Current run hard minimum:

**50 rows**

---

# 26. Schema Compatibility

Required baseline feature missing:

> blocking

Extra columns:

> allowed; ignored for model inference with warning

Baseline numeric feature:

- current values must be numeric/safely coercible
- otherwise blocking

Baseline categorical feature:

- current values are interpreted as categories according to frozen baseline semantics

No current feature-type re-inference.

Every coercion is visible and logged.

---

# 27. Mode A — Labels Unavailable

Target absent.

Allowed:

- schema checks
- missingness
- numeric/categorical drift
- new/disappearing categories
- numeric range changes
- prediction-distribution change
- confidence change

Mandatory statement:

> Actual current predictive performance and calibration cannot be measured because ground-truth labels were not provided.

Forbidden:

- current accuracy claims
- F1 degradation claims
- recall degradation claims
- calibration degradation claims
- “model is failing”
- “retraining is required”

---

# 28. Mode B — Labels Available

Target present, fully labeled and limited to frozen baseline classes.

Includes everything from Mode A plus:

- current performance
- baseline/current deltas
- class-level metrics
- confusion/error analysis
- calibration
- user-selected slice analysis

Partial labels are unsupported.

Unknown target class blocks Mode B analysis.

---

# 29. Raw Data Boundary for Drift

Feature-distribution drift uses **raw observed non-missing values before preprocessing**.

Numeric drift uses:

- raw non-missing numeric values
- before median imputation
- before scaling

Categorical drift uses:

- raw non-missing categories
- before explicit missing-category insertion
- before One-Hot Encoding

Missingness is analyzed separately.

This prevents imputation-induced drift artifacts.

---

# 30. Numeric Feature Drift

Use:

## KS two-sample test
Report:
- KS statistic
- raw p-value
- adjusted p-value

## Wasserstein-1 distance
Descriptive only; remains in feature units.

Do not compare Wasserstein values across unrelated features.

For heavily tied/discrete numeric features, warn that the KS continuous-distribution assumption is imperfect.

---

# 31. Categorical Feature Drift

Use:

- Jensen-Shannon distance, base 2
- chi-square contingency test only when deterministic validity rules pass

Testing algorithm:

1. use raw observed non-missing category counts
2. let `n_base` and `n_current` be the two valid non-missing sample sizes
3. compute the pooling threshold  
   `t = 5 × (n_base + n_current) / min(n_base, n_current)`
4. pool categories whose combined baseline+current count is below `t` into the reserved internal bucket `__MM_OTHER__` for the hypothesis test only
5. raw categories remain visible and are never renamed in the user-facing diagnostic
6. if the pooled `__MM_OTHER__` bucket would still produce an expected cell below 5, merge it into the smallest retained test category
7. require at least 2 resulting test categories
8. build the 2×K contingency table
9. verify every expected cell is ≥5
10. if valid → chi-square
11. otherwise → `INSUFFICIENT DATA`

The pooling membership used for the hypothesis test must be recorded with the feature result for reproducibility.

Jensen-Shannon distance remains available descriptively when the hypothesis test is unavailable.

---

# 32. Feature-Drift Sample Guardrail

Distribution significance testing requires:

- baseline non-missing n ≥30
- current non-missing n ≥30

If not:

> `INSUFFICIENT DATA`

The stricter categorical contingency requirements still apply after this general minimum.

---

# 33. Missingness Monitoring

Per feature show:

- baseline missing %
- current missing %
- percentage-point difference

Build 2×2:

```text
             Missing  Observed
Baseline
Current
```

If both missing counts are zero:

- `NOT DETECTED`
- no p-value
- excluded from BH family

Otherwise:

- expected cells all ≥5 → chi-square
- any expected cell <5 → Fisher exact

Valid p-values enter the BH family.

---

# 34. Benjamini-Hochberg FDR

One monitoring run's BH family contains:

- all valid feature-distribution p-values actually calculated
- all valid feature-missingness p-values actually calculated

Exclude:

- `INSUFFICIENT DATA`
- skipped/no-test cases
- no-p-value cases

Apply:

**Benjamini-Hochberg q = 0.05**

Prediction drift and confidence tests remain outside this family.

---

# 35. Drift Status

Allowed per-signal statuses:

- `DETECTED`
- `NOT DETECTED`
- `INSUFFICIENT DATA`

`DETECTED` means statistical evidence of difference.

It does not mean:

- practically important
- performance degradation
- causal effect

Global red/yellow/green health states are forbidden.

Per-signal statuses are allowed.

---

# 36. Statistical Presentation

Every drift result shows together:

- statistic/distance
- adjusted p-value where available
- baseline n
- current n
- baseline/current visualization

P-values never appear alone.

Default feature ordering may put `DETECTED` first, then larger effect values within the same feature type.

---

# 37. New/Disappeared Categories

Explicitly report:

- new category names
- disappeared category names
- baseline/current category proportions

Unknown categories can be ignored safely by the frozen encoder but must never disappear from reliability reporting.

---

# 38. Numeric Range Change

For numeric features show:

> current non-missing share outside baseline observed [min, max]

Descriptive only.
No significance test.

---

# 39. Prediction Drift

Compare Held-out Baseline Reference predicted-class distribution vs current predicted-class distribution.

Show:

- class shares
- absolute changes
- JS distance
- contingency test if valid
- baseline n
- current n

`NOT DETECTED` means no evidence found in available samples, not proof of identical/stable populations.

---

# 40. Prediction Confidence

Per observation:

> confidence = max predicted class probability

Compare held-out baseline vs current using:

- distribution visualization
- mean
- median
- KS statistic
- p-value
- baseline n
- current n

Without labels:

> confidence shift ≠ accuracy change

---

# 41. Actual Performance — Mode B

For every valid metric:

- Baseline
- Current
- Absolute Δ
- baseline support
- current support

No composite degradation score.

No universal red/yellow/green performance thresholds.

---

# 42. Absent Current Classes

If one or more frozen baseline target classes have zero current support:

- Accuracy may be shown, with class-mix warning
- valid per-class metrics may be shown
- full-class macro comparisons that are no longer comparable are marked unavailable for direct baseline comparison
- invalid ROC-AUC variants are unavailable
- probability metrics must still use the frozen baseline class list/order

Log Loss and multiclass Brier may be calculated with the full frozen class/probability space where mathematically valid, but the UI must state:

> class composition changed; aggregate probability-metric deltas should be interpreted cautiously because the absent class has no current outcome support.

ModelMedic must never compare two macro metrics computed over different class sets as though they were identical quantities.

---

# 43. Performance-Uncertainty Limitation

V1 does not compute bootstrap confidence intervals or significance tests for performance deltas.

Therefore performance comparisons show:

- baseline n
- current n
- class support

Required limitation:

> Small metric differences may reflect sampling variation. ModelMedic V1 does not estimate uncertainty intervals for performance changes.

---

# 44. Calibration

Use:

- Reliability Diagram
- Brier Score
- Log Loss

Brier label:

> probabilistic prediction quality

Never label Brier as simply “Calibration Score”.

No ECE.
No automatic recalibration.

---

# 45. Calibration Binning

Use quantile bins:

| Labeled observations | Bins |
|---:|---:|
| 40–99 | 3 |
| 100–249 | 5 |
| 250–499 | 8 |
| ≥500 | 10 |

Binary/OvR class calibration requires:

- ≥20 positive
- ≥20 non-positive

Otherwise:

> Unavailable — insufficient positive/non-positive observations.

For calibration sample n <250, show:

> Limited-support calibration estimate — empirical rates may be unstable.

Every bin shows its observation count.

Applies to baseline and current calibration views.

---

# 46. Error Analysis

Binary:

- TP
- TN
- FP
- FN
- counts/rates

Multiclass:

- confusion matrix
- common confusion pairs

Example-row tables:

- only included model features
- maximum 50 rows per view
- excluded identifiers must not reappear

---

# 47. Slice Analysis

Mode B only.

Eligible V1 slice columns:

> categorical modelling features already included in the frozen project schema

Slice requires:

**≥30 labeled observations**

Otherwise:

> Insufficient sample size for stable slice analysis.

Always show:

- slice n
- class support
- metrics

Important limitation:

> Slice comparisons are exploratory. ModelMedic does not perform significance testing or multiplicity correction across slices. Apparent differences may reflect sampling variation.

User-requested slice analyses are additive derived results and do not mutate core run results.

---

# 48. Permutation Importance

Calculate on:

- Held-out Baseline Reference
- complete frozen sklearn pipeline
- original raw project feature columns

Do not fragment categorical feature importance into one-hot dummy columns.

Configuration:

- scoring = Balanced Accuracy
- repeats = 10
- random seed = 42

Store:

- mean
- standard deviation

Negative values remain visible.

Negative/near-zero interpretation:

> Shuffling this feature did not reduce held-out Balanced Accuracy on average in these repeats. Negative values can arise from sampling variation, correlated features, or model behaviour and are not causal evidence.

Always label:

> Model reliance estimate — not causal importance.

No SHAP in V1.

---

# 49. Feature Diagnostics

Per feature show relevant:

- baseline distribution
- current distribution
- drift statistic
- adjusted p-value
- effect/distance value
- sample sizes
- missingness change
- new/disappeared categories
- out-of-range share
- permutation importance
- fixed interpretation text

Allowed interpretation:

> This feature is both model-relevant and distributionally shifted and deserves investigation.

Forbidden:

> This feature caused performance degradation.

---

# 50. Run History

Project supports:

Baseline → Run 1 → Run 2 → ...

Track real signals such as:

- F1
- Balanced Accuracy
- Recall
- ROC-AUC
- median confidence
- class shares
- KS/JS
- missing %
- Brier
- Log Loss

Unlabeled runs retain gaps for unavailable performance/calibration.

Never interpolate or invent missing values.

---

# 51. Methodology and Code Versioning

Every run stores:

- methodology_version
- code_version

Historical results are never silently recomputed after methodology/code changes.

---

# 52. Reliability Report

Every analyzed run has a deterministic report generated from stored results.

No LLM.

Interpretation text comes from fixed reviewed templates with computed values substituted.

Report includes:

1. Project
2. Baseline
3. Run metadata
4. Schema/compatibility
5. Data changes
6. Prediction behaviour
7. Confidence
8. Performance or unavailable reason
9. Calibration or unavailable reason
10. Error/class analysis
11. slices if created
12. mandatory limitations

---

# 53. Mandatory Report Limitations

Always state:

- drift does not prove predictive degradation
- predictive performance requires current labels
- statistical significance does not imply practical importance
- feature importance is model reliance, not causality
- small samples may be unstable
- performance deltas have no uncertainty intervals in V1
- slice comparisons are exploratory and uncorrected for multiplicity
- ModelMedic does not establish causality
- a `NOT DETECTED` test does not prove populations are identical

---

# 54. No Retraining Instruction

ModelMedic never automatically says:

> Retrain now.

Allowed:

> Performance is lower than baseline and several reliability signals changed. Investigation is recommended.

---

# 55. Forbidden Composite Scores

Never display:

- Model Health Score
- Trust Score
- Reliability %
- Drift Risk %
- Retrain Probability
- AI Quality Score
- global synthetic red/yellow/green health state

---

# 56. Reproducibility

Store enough to reproduce baseline behaviour:

- seed
- split information
- feature list/types
- target
- class mapping/order
- positive class
- preprocessing config
- classifier config
- weighting mode
- package/runtime versions
- baseline distributions
- missingness/category profiles
- model/preprocessing artifact
- metrics
- methodology/code versions

---

# 57. Artifact Compatibility

Internally generated model artifacts store environment/version metadata.

Before artifact loading:

- integrity/version compatibility must be checked

Known incompatible runtime:

> block loading with a clear compatibility error

Do not silently attempt incompatible model loading.

---

# 58. Security — Product Level

- no uploaded serialized user models
- CSV input treated as untrusted
- stored datasets/artifacts are private
- secrets never committed
- shared/public deployment must not expose one user's uploads to others
- if real user isolation is not implemented, public deployment must use safe read-only/demo protection
- warn users not to upload sensitive personal data to shared demo deployments

---

# 59. Deletion

Deleting a project deletes:

- monitoring runs
- slice analyses
- dataset metadata
- original/canonical datasets
- model/preprocessing artifacts
- reports/results
- associated jobs/metadata

No intentional orphaned data.

Individual run deletion is a V1 SHOULD rather than a core MUST.

---

# 60. Product States

Project:

- DRAFT
- BASELINE_READY
- MONITORING

Run:

- UPLOADED
- VALIDATION_FAILED
- READY
- ANALYZED

No enterprise lifecycle states.

---

# 61. Product Acceptance Criteria

V1 passes when a user can:

1. create a project
2. upload/validate baseline
3. select target/features/types
4. select binary positive class
5. review preprocessing
6. train one supported classifier
7. review CV separately from held-out baseline
8. establish and freeze baseline
9. create Mode A run and receive no performance/calibration claims
10. create Mode B run and receive valid metrics/calibration
11. handle missing required features correctly
12. continue with extra columns as warnings
13. handle unseen feature categories without crashing
14. report new categories
15. reject partial labels
16. reject unknown Mode B target classes
17. apply deterministic drift validity rules
18. apply BH correction only to valid performed tests
19. respect slice guardrails
20. preserve unlabeled history gaps
21. preserve methodology/code version
22. generate deterministic report
23. never show composite health score
24. never issue automatic retraining instruction
25. run end-to-end in Docker

---

# 62. Scientific Acceptance Criteria

Tests must prove:

### Leakage
Held-out/current data cannot change fitted preprocessing/model state.

### Held-out discipline
Official baseline metrics come from held-out reference only.

### Drift fixtures
Known deterministic fixtures produce expected detection/non-detection/insufficient-data outcomes.

### Chi-square validity
Sparse category cases obey the fixed pooling/expected-count rules.

### Missingness testing
Zero/zero skips p-value; Fisher/chi-square switch works correctly.

### BH
Adjusted values match a trusted reference implementation.

### Metrics
Values match scikit-learn reference calculations.

### Frozen class order
All probability metrics use the baseline class list/order.

### Mode A
No performance/calibration/error claims appear.

### Calibration
Bin counts sum correctly and support guardrails are enforced.

### Importance
Uses held-out raw project features through complete pipeline.

### Reproducibility
Same inputs/config reproduce deterministic results within documented library behaviour.

### Wording
Fixed templates cannot produce forbidden Mode A or causal claims.

---

# 63. Final V1 Guardrails

| Rule | Value |
|---|---:|
| Effective baseline total | max(200, 100 × classes) |
| Baseline per class | ≥100 |
| Held-out per class | ≥20 |
| Held-out 20–29 warning | yes |
| Monitoring run | ≥50 rows |
| Feature drift non-missing n | ≥30 per sample |
| Max categories/model feature | 100 |
| Slice labeled n | ≥30 |
| Target classes | binary 2; multiclass 3–10 |
| BH FDR | q = 0.05 |
| Permutation repeats | 10 |
| Random seed | 42 |
| Calibration support | ≥20 positive and ≥20 non-positive |

All are V1 product/methodology guardrails, not universal statistical laws.

---

# 64. Explicit Limitations

- univariate/marginal drift does not detect all joint feature-distribution changes
- KS p-values are imperfect for heavily discrete/tied numeric variables
- drift tests depend on sample size
- large samples may flag tiny changes
- small samples may miss real changes
- prediction/confidence reference uses held-out baseline and can have limited power
- performance deltas have no confidence intervals
- calibration estimates can be coarse at low support
- slice comparisons are exploratory and uncorrected for multiplicity
- permutation importance can be unstable/correlated-feature sensitive
- a weak baseline model limits monitoring value
- partial/delayed labels unsupported
- only categorical modelling features can be used for slices
- no automatic remediation/retraining
- batch only, not real-time
- not a validated enterprise/regulatory monitoring platform

---

# 65. High-Level Technology Direction

Expected:

- React + TypeScript frontend
- FastAPI/Python backend
- scikit-learn/Pandas/NumPy/SciPy
- persistent database
- private internal artifact storage
- Dockerized deployment

Exact architecture is documented separately.

---

# 66. Final Scope Lock

Locked:

- tabular CSV classification
- binary + multiclass
- Logistic Regression
- Random Forest
- Gradient Boosting
- internal model training
- 80/20 stratified split
- 5-fold stratified development CV
- seed 42
- median numeric imputation for all models
- explicit categorical missing handling
- one-hot encoding
- StandardScaler only for Logistic Regression
- Standard/Balanced weighting
- frozen model/preprocessing/types/class order
- Mode A / Mode B
- raw non-missing feature drift
- separate missingness drift
- KS + Wasserstein numeric
- JS + deterministic chi-square categorical
- Fisher/chi-square missingness test rule
- BH q=.05 on valid performed feature tests
- no severity bands
- prediction drift
- confidence drift
- label-gated performance/calibration
- deterministic calibration bins
- Brier + Log Loss
- no ECE/recalibration
- permutation importance
- no SHAP
- labeled categorical slice analysis
- exploratory slice limitation
- run history
- methodology/code versioning
- deterministic reports
- no composite health score
- no AutoML
- no automated retraining
- no LLM dependency
- no enterprise MLOps expansion

---

# 67. Remaining Decisions

No unresolved core product or ML methodology question remains.

Only implementation/architecture decisions are allowed to remain, such as:

- concrete database schema details
- artifact-storage mechanics
- API schemas
- exact resource/upload limits
- deployment provider
- public demo access mechanism
- frontend visualization library
- CI implementation

---

# Final Status

## **MODEL MEDIC V1.0 PRD — LOCKED**

This document is the authoritative V1 product/methodology specification.

Implementation, architecture and UI must conform to it unless an explicit approved PRD revision is made.


---

# PRD 1.0.1 Methodology Patch

This patch was added after the final technical-architecture audit.

It does **not** change ModelMedic scope or product behaviour.

It corrects one categorical drift-testing detail:

- the previous fixed pooling rule (`combined count < 10`) did not guarantee valid chi-square expected counts when baseline and current sample sizes were strongly unbalanced;
- V1.0.1 therefore uses the sample-size-aware pooling threshold defined in Section 31;
- `__MM_OTHER__` is a reserved internal testing label and must not collide with user category values;
- the actual categories pooled for a test are persisted for reproducibility.

All other locked V1 product and ML methodology decisions remain unchanged.
