# CardioLens

A heart-health guidance tool for the general public, built on a cross-cohort validation study of the UCI Heart Disease data (Cleveland, Hungary, Switzerland, Long Beach VA).

It answers one question in plain language: does my situation deserve a closer look by a doctor, and how far can I trust that answer?

## What it does

- Symptom check: plain-language questions turn into a band (lower concern, worth getting checked, see a doctor soon) with the share of similar patients who really had artery blockage, and how that share varied between hospitals.
- Referral check: the same flow for people sent for a heart check without chest pain.
- Risk-factor check: rule-based review of blood pressure, cholesterol, sugar, BMI, smoking, activity, using published guideline cut-offs. No prediction is made for people without symptoms.
- Emergency screen first, plus safety rules that can raise a band but never lower it.
- Clinic calibration: upload a small labelled CSV and the baseline of the model is shifted to your local disease rate. The file is never stored.
- Evidence page: leave-one-hospital-out AUC, calibration curves, band statistics, original study protocol, data quality.
- Privacy by design: the API is stateless and history lives in the browser.

## Design decisions taken from the study

| Finding | Product decision |
| --- | --- |
| Pooled accuracy hides large hospital-to-hospital differences | Every reported number comes from leave-one-hospital-out testing |
| Calibration shifts with local disease prevalence | Bands and observed rates instead of a single percentage; optional local recalibration |
| Predictors with 95 to 99 percent missingness cannot be used elsewhere | Only 7 or 10 widely available inputs; unknown inputs are allowed and lower the confidence label |
| Logistic regression stays better calibrated than a random forest | Deployed model is regularised logistic regression; the forest is kept for the comparison table |
| Asymptomatic patients in referred data are often disease-positive | The option "no chest pain" exists only on the referral pathway, and the symptom pathway forces a floor for exertional pain |
| Cholesterol recorded as 0 means not measured | Zeros in cholesterol and blood pressure are recoded to missing before any fitting |

## Run it

Requirements: Python 3.11+, Node 20+.

    cd backend
    pip install -r requirements.txt
    python -m app.training
    pytest
    uvicorn app.main:app --port 8000

    cd ../frontend
    npm install
    npm run dev

Open http://localhost:5173. For one command in development run `./run_dev.sh`.

`python -m app.training` downloads the four processed UCI files (UCI first, Hugging Face mirror second) into `backend/data/raw`. If you are offline, place `processed.cleveland.data`, `processed.hungarian.data`, `processed.switzerland.data` and `processed.va.data` there yourself. Use `--require-real` to refuse the demo fallback, `--skip-paper` for a faster run, `--synthetic` for a throwaway demo model. Any model not trained on the real files shows a demonstration banner in the app.

Quick check of the cholesterol data issue:

    python -c "from app import data; r=data.pd.concat([data.parse(data.fetch(s),s) for s in data.FILES]); print((r.chol==0).groupby(r.site).sum())"

## Deploy

    docker build -t cardiolens .
    docker run -p 7860:7860 cardiolens

The image trains on the real data at build time and fails if it cannot get it. Works on Hugging Face Spaces (Docker).

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | /api/health | readiness |
| GET | /api/model-card | metrics, bands, coefficients, data quality |
| POST | /api/assess | symptom or referral assessment |
| POST | /api/wellness | risk-factor check |
| POST | /api/clinic/calibrate | local recalibration from a CSV |
| GET | /api/clinic/template | CSV template |

## Limits

Records are from the 1980s and every patient was referred for angiography. The tool estimates narrowed arteries, not heart-attack risk. External data had few women and few young people. It is a research prototype and not a medical device.
