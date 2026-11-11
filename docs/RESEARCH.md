# Research methodology

## Reproduction protocol (as published)

- Development cohort: Cleveland (303). External cohorts: Hungary (294), Switzerland (123), Long Beach VA (200). Outcome: angiographic label above 0.
- Models: full logistic (13 predictors), portable logistic (10), full random forest, portable random forest.
- Preprocessing inside each training fold: median imputation and standardisation for numeric predictors, most-frequent imputation and one-hot encoding for categorical ones.
- Logistic regression with L2 penalty and fixed C = 1. Random forest with 500 trees, maximum depth 5, minimum leaf 5, square-root feature sampling. No oversampling or class weighting.
- Repeated stratified 5-fold cross-validation x 10, out-of-fold probabilities averaged per record, seed 20260904. Each model is refitted once on Cleveland and applied unchanged to every external cohort.
- Metrics: AUC, average precision, sensitivity, specificity, precision, F1, balanced accuracy at 0.5, Brier score, calibration intercept and slope, bootstrap 95% intervals (up to 2000 resamples).
- External cohorts are never used to fit anything.

Verified by test: flipping every external label leaves the internal result unchanged and changes the external one.

## Additional analyses (not in the paper)

Decision curve analysis, recalibration experiments (prevalence adjustment, update study, full intercept and slope update), permutation importance, verdict rules of thumb. Each is labelled as an extension in the dashboard and in the PDF.

## Provenance labels

| Label | Meaning |
| --- | --- |
| Reproduced from the paper | UCI records, paper configuration, zero values kept as recorded |
| New experiment | Any other configuration, including zero-value recoding and uploaded data |
| Synthetic demonstration | Generated data, never real patients |

Paper values for 4 internal models and 6 external model-cohort pairs are stored in `app/research/paper.py` and compared with each reproduction run.

## Items to check in the paper before submission

1. Cholesterol (and blood pressure) values of 0 appear to be treated as real values. Run the experiment with and without recoding and report both.
2. Section 3.2 says two predictors were removed but also says ten remain from thirteen; the ten-predictor model drops three (ca, thal, slope).
3. The literature review says fluoroscopy vessel count, ST slope and thalassemia were "documented in only 95% to 99%" of external patients. They were missing in those proportions.
4. Maximum heart rate is listed among resting measurements but comes from exercise testing.
5. "Mobile instrument feature set" should read portable feature set.
6. The Discussion cites a higher pooled external AUC for the random forest that the Results do not report.

## Deployed model (separate from the replication)

The inference model is a regularised logistic regression with C chosen by inner cross-validation on log-loss, fitted on all four cohorts. Its reported performance is leave-one-hospital-out only. Outputs are bands with the observed share of disease in each band and its range across hospitals, not a single probability. Explanations are exact linear contributions, equal to SHAP values for a linear model with independent features. The SHAP library is not used.

## Uncertainty and second opinion (version 1.1)

- Score range: 200 logistic models are fitted to bootstrap resamples of the preprocessed training matrix with the chosen regularisation. A patient's 5th to 95th percentile score across those models is shown as the plausible range. It reflects sampling variability of the coefficients, not preprocessing variability or any bias in the data.
- Second opinion: a random forest (500 trees, depth 5) trained on the same inputs. Its band cut-offs come from its own leave-one-hospital-out predictions with the same rules as the logistic model. Disagreement widens the stated uncertainty and lowers the confidence label.
- Both are explained to the patient in plain language and neither can lower urgency.
