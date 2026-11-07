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

## Platform layer (v2)

Added on top of the original stateless tool; the public `/api/assess`, `/api/wellness` and clinic calibration endpoints are unchanged.

- Accounts and roles: patient, clinician, clinic administrator, researcher. Public registration only creates patients. Staff are created by an administrator. Roles are enforced on the server and clinicians only see patients of their own clinic.
- Stored patient assessments (symptom and wellness), history, CSV export, clinician notes with a "reviewed" status, and provenance labels (patient-reported, model-generated, clinician-reviewed).
- Research engine (from TransportLab): upload a CSV, choose outcome, site and development site, and get external validation, calibration, decision curves, update study, missingness and subgroups. Experiments are stored per researcher and labelled uploaded or synthetic_demo. Decision curves and the update study are additional analyses, not results of the original paper.
- Audit log, login rate limiting, scrypt password hashing, JWT, upload limits, structured logging, database-aware health check.

Run with Postgres: copy `.env.example` to `.env`, fill it in, then `docker compose --env-file .env up --build`.
Tests: `cd backend && pytest`.

## Not done yet

React screens for sign-in, patient dashboard, clinical workspace and research dashboard (the API is ready); PDF reports; Alembic migrations (tables are created at start-up); symptom-duration and medical-history fields; appointments; end-to-end browser tests. The reproduction of the paper's exact numbers needs the real UCI files, which could not be downloaded in the build environment.

## Limits

Records are from the 1980s and every patient was referred for angiography. The tool estimates narrowed arteries, not heart-attack risk. External data had few women and few young people. It is a research prototype and not a medical device.
