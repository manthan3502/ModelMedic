# M7 direct scientific audit

The original locked PRD, architecture, UI/UX and milestone plan remain authoritative.
This record maps inspected code to those rules; it does not introduce methodology.
Code was inspected directly, including publication and presentation paths, before
the tests below were used as corroborating evidence. No scientific formula,
classifier parameter, split, threshold, reference population or version was changed.

| Locked rule | Inspected implementation | Corroborating test families |
|---|---|---|
| Baseline max(200, 100 × classes), 100/class; 2–10 classes; actual held-out minimum 20/class | `domain/datasets.py:target_info`, `science/baseline.py:split_indices`, `guard_heldout` | datasets, baseline, hardening minimum 2/3/10 classes and imbalance, training guard failure |
| 80/20 stratified seed 42; five shuffled stratified development folds; fresh complete pipeline per fold; final fit only development | `science/baseline.py:train` | baseline split membership and fit-spy leakage tests; real training reference/split artifact tests |
| Median numeric imputation; LR-only StandardScaler; explicit categorical missing value; frozen unknown handling | `RawFeatures`, `make_pipeline`, `fit_pipeline` | all six model/weighting leakage tests; all-missing categorical / near-missing numeric / constant tests; unseen-level regression |
| Exactly three classifiers and Standard/Balanced; GB fold-local sample weights | `make_pipeline`, `fit_pipeline`; request schemas | all classifier/weighting tests and 12 real-stack combinations |
| Explicit binary positive class; immutable ordered probability class columns | `evaluate`, `predict_probabilities`; manifest checks in monitoring/slices | reversed probability order, class-order mismatch, frozen manifest and positive-index-zero known answers |
| Binary and multiclass metric sets; undefined values have reasons; full unscaled multiclass Brier sum | `evaluate`, `labeled.performance` | sklearn known answers, confusion matrices, one/multiple absent classes, defined zero vs unavailable |
| Empirical quantile reliability bins 3/5/8/10 at n 40/100/250/500; 20 positive and 20 non-positive; tied boundaries combined; n<250 caution | `calibration` | all support and bin boundaries, 19/20 event guards, tied probability accounting |
| Held-out raw-feature permutation importance; Balanced Accuracy; 10 repeats; seed 42; mean/SD; negatives preserved | `train` | fit/importance spies and real persisted held-out evidence |
| Raw observed-value feature tests before fitted preprocessing; no current refitting | `monitoring.analyze_mode_a`, `numeric_drift`, `categorical_drift` | fitted-imputer/scaler/encoder invariance, raw missing-value boundary, Mode B single-inference tests |
| Two-sided KS and Wasserstein; valid observed n>=30 in both samples; units and ties cautions | `numeric_drift` | SciPy reference tolerance, 29/30 boundary, constants/ties/overflow bins |
| JS distance base 2 on raw union; dynamic chi-square pooling; threshold 5(nB+nC)/min(nB,nC); expected cells>=5; at least two groups; no Yates correction | `categorical_drift` | SciPy JS/chi-square reference, unbalanced counts, rare-group merging and OTHER-name collision |
| Missing/observed 2×2 table; chi-square if all expected>=5, otherwise two-sided Fisher; both zero missing skip p | `missingness` | SciPy reference on both paths, zero/all missing cases |
| BH q=.05 over valid feature distribution and missingness p-values together; prediction/confidence outside that family | `correct_family`, `analyze_mode_a` | trusted vector and SciPy FDR tolerance, invalid/zero-missing exclusion, family size |
| Predicted shares in frozen order against held-out; maximum probability confidence; separate overall comparisons | `predict_probabilities`, `analyze_mode_a`, `confidence_drift` | class-order and raw-boundary fixtures; real frozen inference/reference tests |
| Mode A has no current performance/calibration/errors/slices claims | labeled route guards, report templates and frontend unavailable states | scientific claim-safety tests, PostgreSQL route guards, browser checks |
| Mode B absent classes retain full probability space; unsupported macro/BA/AUC values unavailable; no uncertainty intervals or causal attribution | `labeled.performance`, `matrix`, `analyze_mode_b` | binary/multiclass known answers, multiple absent-class fixtures, bounded error row references |
| Categorical included frozen slices only, n>=30, raw spelling/missing groups, All rows reference; no tests/fairness verdict | `science/slices.py`, `jobs/slices.py`, diagnostics routes | 29/30 threshold, additive immutable publication, idempotence/concurrency, source hash guard |
| One stored historical signal; Monitoring Date / created timestamp / UUID order; Mode A gaps; no interpolation, smoothing or forecast | `services/trends.py`, `Diagnostics.tsx:TrendChart` | database ordering and persisted-value tests, frontend gaps, browser chart/table review |
| Fixed, versioned immutable reports from saved facts; additive slices do not rewrite core report; nine mandatory limitations | `reporting.py`, `report_store.py`, migration triggers | deterministic structure/claim safety, template-version behavior and PostgreSQL immutability |
| Worker-only trusted internal joblib; hash/version/Python minor/exact sklearn before deserialization; DB and stored manifest agree | `jobs/artifacts.py`, training/monitoring/slice publication | corruption/missing/version mismatch tests, manifest/class/schema/fingerprint guards; API has no artifact upload route |

The only artifact-loader change is a reviewed missing-object diagnostic before
deserialization. M7 resource supervision changes execution boundaries and failure
handling, not scientific results. Published results still commit only through the
same PostgreSQL owner-token/attempt/unexpired-lease transaction.

The scientific library pins remain numpy 2.3.3, scipy 1.16.2, pandas 2.3.3,
scikit-learn 1.7.2 and joblib 1.5.2. Numerical reference tests use explicit relative
and absolute tolerances rather than alternate handwritten methodology.

Evidence and remaining external checks are recorded in `m7-verification.md` after
the final gate. A locally verified deployment image is not evidence of a live URL.
