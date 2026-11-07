# TransportLab

A tool that answers a general question: will a clinical risk model built at one site still work at another?

Upload one table with an outcome column and a site column. TransportLab trains on a chosen development site, tests on every other site without refitting, and reports:

- ranking (AUC with bootstrap intervals) for logistic regression and random forest
- calibration (intercept, slope, curves) and a plain-language verdict per site
- automatic selection of "portable" features, those with at most 30% missing at every site
- decision-curve analysis, with and without prevalence adjustment
- how many local labelled cases it takes to repair calibration (intercept-only versus intercept and slope)
- missing-data heatmap and subgroup performance

It works for any binary outcome and any set of sites. Two demos are bundled: a synthetic four-hospital dataset and the UCI Heart Disease cohorts.

## Run

    pip install -r requirements.txt
    python app.py
    pytest

Open http://localhost:5000, choose a demo or upload your own CSV. A Dockerfile is included for Hugging Face Spaces or any container host.

## Research basis

Detrano et al. 1989 (international validation of a CAD model); Steyerberg et al. 2004, Stat Med 23:2567; Vergouwe et al. 2017, Stat Med, doi:10.1002/sim.7179 (updating hierarchy); Steyerberg 2019, Clinical Prediction Models, ch. 20; Vickers and Elkin 2006 (decision curves); Van Calster et al. 2019, BMC Med 17:230 (calibration); TRIPOD+AI 2024.

## Design notes

- Portable features are chosen by missingness only (at most 30% missing at every site); outcomes at other sites are never used for selection or fitting.
- Analyses run in a background thread, so run the server with one worker (the Dockerfile does).
- Set SHOW_RECENT=0 on shared deployments to hide the list of earlier reports. Reports contain aggregates only, never uploaded rows.
- Guards: continuous outcomes are rejected, ID-like and constant columns are dropped, near-perfect single predictors raise a leakage warning, and sites with too few rows or events are marked as unjudgeable.

## Limits

Recalibration repairs average risk, not ranking. Verdict thresholds (AUC drop above 0.08, intercept beyond 0.5, slope outside 0.8 to 1.2) are rules of thumb. Not a medical device.
