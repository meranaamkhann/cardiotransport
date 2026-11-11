# CardioLens

An AI-assisted heart-health platform for patients, clinicians and researchers. It keeps four kinds of information strictly apart: patient-reported, rule-based triage, model-generated, and clinician-reviewed. It is not a diagnostic system.

## Model refinements in version 1.1

- Every score carries a plausible range from 200 bootstrap-resampled logistic models, and a wide range lowers the confidence label.
- A random forest built on the same inputs gives a second opinion. When it places the patient in a different band, the result says so and confidence drops. Its agreement with the logistic model is reported in the model card and the registry.
- The regularisation grid for the logistic model is finer (nine values) and is chosen by inner cross-validation on log-loss.
- Accuracy is still reported only as leave-one-hospital-out. Whether these changes improve it on the real UCI records is measured by `python -m app.training`, so check the held-out table it prints.
- Researchers can compare two completed experiments side by side, for example the paper protocol with and without zero-value recoding.

| Area | What it does |
| --- | --- |
| Patients | Profile, step-by-step symptom assessment with an emergency pathway and draft saving, wellness (risk-factor) review, measurements with guideline status labels and trends, urgency timeline, appointments, PDF and CSV export, full data download, account deletion, a log of who viewed their record, consent-based clinic sharing, larger-text mode |
| Clinicians | Review queue ordered by urgency with filters and emergency banner, patient directory and records, clinical review, encrypted notes, appointments, PDF reports, per-clinic model calibration |
| Clinic administrators | Staff management, audit log, calibration |
| Researchers | Paper-protocol replication, uploads of multi-site datasets, 4-model cross-hospital validation, calibration, decision curves, recalibration, missing-data and subgroup analysis, PDF and CSV reports, model registry |
| Public | Landing page, anonymous quick check, evidence page with the model card |

Read `docs/ARCHITECTURE.md` for the design, `docs/RESEARCH.md` for the methodology and the issues found in the paper, and `docs/DEPLOYMENT.md` for operations.

## Run locally

Requirements: Python 3.11+, Node 20+.

    cd backend
    pip install -r requirements.txt
    python -m app.training --skip-paper
    python -m app.seed
    uvicorn app.main:app --port 8000

    cd ../frontend
    npm install
    npm run dev

Open http://localhost:5173. `./run_dev.sh` does all of this in one command.

`python -m app.training` downloads the four processed UCI files (UCI first, Hugging Face mirror second) into `backend/data/raw`. Offline, place `processed.cleveland.data`, `processed.hungarian.data`, `processed.switzerland.data` and `processed.va.data` there. Use `--require-real` to refuse the synthetic fallback. Any model not trained on the real files shows a demonstration banner in the app.

`python -m app.seed` creates a synthetic demo clinic (code `DEMO01`). All accounts use the password `DemoPass123`: `patient1@`, `patient2@`, `patient3@`, `clinician@`, `admin@` and `researcher@demo.cardiolens.test`. Seeding is refused when `CARDIOLENS_ENV=production`.

## Run with Docker (PostgreSQL)

    cp .env.example .env
    docker compose up --build

Set `POSTGRES_PASSWORD` and `SECRET_KEY` in `.env`. The app is served on http://localhost:8080. Migrations run on start. Set `ALLOW_SYNTHETIC=1` to build without downloading the UCI files (demonstration only).

## Tests

    cd backend && python -m pytest        # 66 tests: auth, authorization, assessments, clinic isolation, uncertainty and second opinion, data export and deletion, research methodology, uploads, reports, migrations, end-to-end workflow
    cd frontend && npm test               # 27 tests: API client, routing, the symptom stepper, draft restore, account deletion, queue filters, run comparison, accessibility preferences, assessment and research views rendered from real API responses
    cd frontend && npm run build          # type-check and production build

## Reproduce the paper

Sign in as a researcher, open Experiments, choose Paper protocol with the UCI source and 2000 bootstrap resamples. The run follows the published configuration (Cleveland development cohort, four models, repeated stratified 5-fold CV x 10, seed 20260904, fixed hyperparameters) and prints a side-by-side comparison with the values reported in the paper. A second run with the zero-value recoding switched on shows what changes when impossible cholesterol and blood-pressure values of 0 are treated as missing. That run is labelled a new experiment, not a reproduction.

## Honest limits

- The research model learned from 1980s records of patients already referred for angiography. It estimates narrowed arteries, not heart attack risk, and is not a screening tool for the general public.
- Nothing here has been clinically validated.
- The login rate limiter and experiment queue live in one process. Scale out only after moving them to Redis or a job queue.
- Browser end-to-end tests (Playwright) are not included; the end-to-end workflow is tested through the API.
