# Baseline methodology — baseline-v1

M2 implements the four locked specifications without model selection, monitoring,
drift, recalibration or hyperparameter search. These are implementation details
of that contract; the locked documents remain authoritative.

## Environment and reproducibility

Python 3.12; scikit-learn 1.7.2; NumPy 2.3.3; SciPy 1.16.2; pandas 2.3.3;
joblib 1.5.2; PyArrow 21.0.0. Exact resolved dependencies are in uv.lock.
Docker fixes OpenMP/OpenBLAS/MKL thread counts to one; forest and permutation
importance also use n_jobs=1. Seeds are 42. Numerical reproducibility is within
the pinned library/runtime behaviour, not a cross-platform bitwise promise.

The build records its Git SHA and dirty flag; the manifest also records a digest
of backend source. Dirty verification builds are identifiable. After the milestone
commit, rebuild from the clean checkout to stamp subsequent attempts with that SHA.
Python patch version is recorded; loading requires the same Python minor and exact
scikit-learn version, supported artifact format, and the trusted SHA-256.
Only the dedicated worker imports the deserialization helper.

## Split and fitting

Require max(200, 100 × class count) rows and 100/class before splitting.
train_test_split(test_size=0.2, stratify=y, random_state=42) creates Development
and Held-out Baseline Reference membership. The actual held-out count must be
at least 20/class; 20–29 emits the required support warning. No model artifacts
are published if this check fails. Stable canonical row IDs persist membership.

StratifiedKFold(n_splits=5, shuffle=True, random_state=42) runs only within
Development. Each fold constructs and fits a fresh complete pipeline. The final
pipeline is separately fitted on all Development rows. CV is diagnostic only;
fold values, mean, sample SD (ddof=1), minimum and maximum are retained. A missing
fold metric leaves the aggregate unavailable with a reason.

Frozen semantic conversion is inside the sklearn Pipeline. Numeric values are
coerced using the reviewed feature types, followed by median imputation for all
models and StandardScaler only for Logistic Regression. A numeric input with no
observations in a fitting fold cannot supply a median: training fails with a
reviewed explanation instead of inventing an imputation value.

Categorical values remain lexically distinct. Internal `v:` prefixes distinguish
observed strings from the explicit `m:` missing category without collisions.
OneHotEncoder(handle_unknown='ignore', sparse_output=False, dtype=float64) learns
categories only from the fitting partition. Future unseen categories cannot
change the encoder. No current-data workflow is implemented in M2.

## Fixed classifier settings

All unlisted estimator options remain the documented defaults of the pinned
scikit-learn version. No setting is searched or selected from evaluation results.

| Classifier | Explicit fixed settings |
|---|---|
| Logistic Regression | C=1, penalty=l2, solver=lbfgs, max_iter=1000, tol=1e-4, random_state=42 |
| Random Forest | 100 trees, criterion=gini, max_depth=None, min_samples_split=2, min_samples_leaf=1, max_features=sqrt, bootstrap=True, random_state=42, n_jobs=1 |
| Gradient Boosting | loss=log_loss, learning_rate=0.1, 100 estimators, subsample=1, criterion=friedman_mse, min_samples_split=2, min_samples_leaf=1, max_depth=3, max_features=None, random_state=42 |

Standard weighting uses no weighting. Balanced uses class_weight='balanced' for
LR/RF. Gradient Boosting receives compute_sample_weight('balanced', fitting_y).
Each fold computes its own weights from its fitting partition. No resampling.

## Metrics and frozen class space

The fitted classifier's classes_ order is persisted, along with the explicit
binary positive label. Probability columns, log loss, Brier, ROC-AUC, AP and
calibration use that order, including when the positive class is column zero.

Binary: accuracy, balanced accuracy, precision, recall, F1, ROC-AUC, Average
Precision, log loss, binary Brier and confusion matrix. Multiclass: accuracy,
balanced accuracy, macro precision/recall/F1, weighted F1, per-class metrics/support,
macro OvR ROC-AUC, log loss, multiclass Brier and confusion matrix.

Binary Brier is mean((p_positive - y_positive)^2). Multiclass Brier is
mean(sum_k((p_k - indicator(y=k))^2)), without division by the class count
(range 0–2). Log loss uses the frozen probability index and machine-epsilon
clipping. Undefined denominators produce null plus a reason, not fake zero.
Defined zero remains zero. Macro summaries require defined frozen-class components.

## Calibration and reliance

Held-out quantile bins: 40–99 rows → 3, 100–249 → 5, 250–499 → 8, 500+ → 10.
Use unique quantile edges, left boundary assignment and omit empty bins. This
preserves ties; the actual occupied bin count can be smaller than requested.
Every observation appears in exactly one bin. Store mean probability, observed
rate and count. Binary/OvR curves require at least 20 positive and 20 non-positive
observations. Below 250 labeled rows show the locked limited-support warning.
Multiclass exposes one curve per frozen class. No ECE or recalibration.

Permutation importance uses the original held-out columns through the complete
pipeline, scoring='balanced_accuracy', n_repeats=10, random_state=42, n_jobs=1.
Persist mean and sklearn repeat SD; preserve negatives. SD whiskers are not
confidence intervals. Label: “Model reliance estimate — not causal importance.”

## Persistence and lifecycle

Each worker execution, including a recovered lease attempt, has its own snapshot
and write-once prefix. Snapshots may be TRAINING/FAILED while computation is
incomplete; only TRAINED can become ESTABLISHED. The existing owner/attempt/lease
fence protects atomic job/result publication. Failed or stale workers cannot
publish an establishable model. Artifacts are private and server-addressed.

Persist pipeline.joblib, manifest.json, results.json, heldout.parquet and
split.parquet. Held-out data contains original features, row ID, y_true, y_pred,
probabilities in frozen order and confidence. PostgreSQL retains the scientific
results and provenance; viewing results never refits or recomputes them.

The fingerprint covers canonical dataset SHA-256, target, positive class,
ordered included features/types, classifier and weighting. Draft changes require
discard confirmation. Invalidate database references before deleting old objects;
a rollback cannot delete a valid model. If old-object deletion fails after commit,
a sanitized warning is logged; the unreferenced private prefix cannot be established
or loaded and is removed with draft project deletion. A new committed upload is
never deleted as compensation for that cleanup failure. Establishment atomically checks the
current fingerprint and dataset and freezes snapshot/project state. All existing
baseline mutation routes share the lifecycle guard and reject established projects.

Configured input caps remain computational guardrails, not deployment capacity
promises. This milestone does not claim production throughput or worst-case
memory/latency; deployment sizing remains subject to the locked compute-budget gate.


## M3 monitoring: reference and input boundaries

Methodology `monitoring-v1` uses the established snapshot's ordered feature list,
semantic types and probability classes. Current CSVs share the baseline's empty /
whitespace-only missing policy. Literal missing-like tokens remain observed values;
invalid frozen numeric values block validation. Categories are never trimmed or
re-inferred. A target column must be absent for Mode A. Partial labels and unknown
classes block validation; complete valid labels identify Mode B, whose analysis is
not implemented in M3. At least 50 current rows are required.

The worker verifies canonical SHA-256/schema, model manifest/hash/version and the
exact snapshot configuration fingerprint before frozen inference. It calls only
predict/predict_proba; it never fits preprocessing or a classifier. All valid raw
baseline rows define feature distribution/missingness references. The persisted,
hash-verified M2 held-out predictions/confidence define model-behavior references;
baseline behavior is never inferred again during monitoring.

## M3 statistical parameters

Pinned SciPy 1.16.2 calls are explicit:

- `ks_2samp(..., method="auto")`
- `chi2_contingency(..., correction=False)`
- `fisher_exact(..., alternative="two-sided")`
- `false_discovery_control(..., method="bh")`
- `jensenshannon(..., base=2)` (distance, not divergence)
- `wasserstein_distance(...)` (Wasserstein-1 in the original feature units)

Numeric tests use raw observed non-missing numbers before median imputation or
scaling. Numeric/categorical distribution tests require 30 observed values in each
sample. Tied/discrete numeric inputs carry the continuous-KS-assumption caution.
Range-outside share uses the full baseline observed [min,max] and is descriptive.
Wasserstein magnitudes are never ranked across unrelated features.

Categorical tests use raw observed non-missing counts before missing-category
insertion/OHE. With n_base and n_current, t = 5*(n_base+n_current)/min(n_base,n_current).
Categories whose combined counts are below t enter a test-only internal bucket.
If that bucket's smallest expected cell is below 5, merge its members into the
smallest retained category (combined count; lexical tie-break). Require at least
two resulting groups and every expected cell >=5 before chi-square. Otherwise
INSUFFICIENT DATA; descriptive base-2 JS remains available when both samples exist.
Internal group IDs distinguish the pooled bucket from literal user __MM_OTHER__.
Persist raw category shares, new/disappeared names, threshold, membership and
expected cells; raw category reporting is unchanged.

Missingness is a separate 2x2 missing/observed comparison. Both missing counts zero:
NOT DETECTED, no p-value. Otherwise all expected cells >=5 uses chi-square; any
smaller cell uses two-sided Fisher. Persist missing percentages and signed pp delta.
One run's feature BH family combines only actually calculated valid distribution
and missingness p-values, excludes insufficient/no-p/zero-zero cases and uses q=.05.
Persist family size and adjusted p on each feature signal. DETECTED requires
adjusted p <.05; NOT DETECTED is neutral evidence, not proof of identical populations.

Prediction shares use frozen class order, base-2 JS and the same categorical
validity algorithm. Confidence is max class probability, with means, medians and
KS. These two overall comparisons stay outside feature BH, using their raw p for
status. KS comparisons require 30 values per sample. They cannot measure accuracy
or calibration without labels.

## M3 immutable visualization and publication

Worker-prepared numeric plots use ten equal-width baseline-derived bins plus
explicit overflow bins, expanding constant references by max(abs(value)*.01,.5).
Confidence uses ten fixed bins on [0,1]. Normalize each sample by its own observed
count and persist counts/shares and boundaries. Category/prediction charts render
persisted raw shares. The frontend formats values but computes no statistical or
histogram values. Tables accompany charts.

Each attempt publishes to a private server-generated prefix. Job finalization,
per-feature rows, run results, provenance and ANALYZED transition share one fenced
PostgreSQL transaction. Results remain unavailable before that transaction commits.
An analyzed run cannot be re-uploaded or re-analyzed; database triggers protect
published run/feature updates and frozen run bindings. Run deletion checks active
jobs and leaves recoverable deletion_pending state if object cleanup fails.
History sorts descending monitoring date, creation timestamp, run ID.

Fixed Mode A result templates state: Actual current predictive performance and
calibration cannot be measured because ground-truth labels were not provided.
Confidence change does not prove accuracy or calibration changed. No current
outcome metrics, calibration, errors, slices, severity or retraining instructions
are produced. Full deterministic report export remains the planned M5 work.
