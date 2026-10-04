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
