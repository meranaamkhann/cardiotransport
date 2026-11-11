# Architecture

## 1. The two starting codebases

| | CardioLens v1 | TransportLab |
| --- | --- | --- |
| Purpose | Public heart-health check | Researcher tool for testing whether a clinical model transports across sites |
| Stack | React + TypeScript + Vite, FastAPI, scikit-learn | Flask, Jinja templates, vanilla JavaScript, scikit-learn, statsmodels |
| State | Stateless API, browser localStorage | JSON report files on local disk |
| Auth | None | None |
| ML | Logistic regression trained on all four cohorts, evaluated leave-one-hospital-out; random forest only in the paper protocol | Generic: logistic and forest, full and portable feature sets, bootstrap CIs, calibration, decision curves, update study, subgroup AUC |
| Tests | 18 backend tests | 6 tests (all pass) |
| Deployment | Single Dockerfile | Dockerfile with gunicorn |

## 2. Feature inventory

CardioLens v1: anonymous symptom and referral check, wellness check, local calibration through a CSV (stored in the browser), evidence page.

TransportLab: CSV upload with column mapping, `analyze()` pipeline (portable feature rule at 30% missingness, internal repeated CV, external validation per site, pooled metrics), calibration intercept and slope, prevalence-adjusted decision curves, update study with 10 to 80 local cases, verdicts by rules of thumb, sex or group subgroup table, a demo on the UCI data, saved HTML reports.

## 3. What was retained, integrated, redesigned and discarded

| Decision | Item |
| --- | --- |
| Retained | Inference engine and training script, leave-one-hospital-out evaluation, band logic with safety floors, wellness thresholds, anonymous quick check, FastAPI + React + TypeScript stack |
| Integrated from TransportLab | Metric set, calibration terms, bootstrap intervals, decision curves, update study, verdict rules, subgroup analysis, portable-feature rule, upload-driven experiments. Reimplemented inside `app/research`, with a fast rank-based AUC, JSON-safe output and background jobs |
| Redesigned | Persistence (PostgreSQL), accounts and roles, local calibration (now a per-clinic database record applied server-side, not browser state), routing (React Router), data fetching (TanStack Query), charts (Recharts), reports (server-side PDF with provenance sections) |
| Kept separate | `app/research` has no import from the patient-facing code and can run on its own. Research datasets and patient records live in different tables and are never joined |
| Discarded | Flask UI and templates, JSON-file report storage, Flask debug server, synchronous request-time analysis |

## 4. Weaknesses found

Technical:
- CardioLens v1 had no authentication, no persistence and kept calibration in the browser, so a clinic could not apply it to its patients.
- TransportLab has no authentication or access control, stores reports as unprotected files, analyses synchronously inside the request, and its `__main__` starts Flask with `debug=True`.

Statistical:
- The paper treats a cholesterol of 0 as a real measurement (its Figure 1 shows 0% missing cholesterol for Switzerland). In the UCI files zero means not measured. Treating it as a number distorts standardisation and probably contributes to the Switzerland calibration shift. The replication runs both ways so the effect can be measured.
- Pooled external AUC mixes cohorts with prevalence from 36% to 93%, so cohort-specific results are the main evidence.
- Calibration slopes of 1.5 for the random forest show under-confident probabilities, which is why the deployed model is logistic.
- TransportLab's prevalence-adjusted decision curve uses the target site's observed outcome rate. The dashboard labels it as an upper bound.
- In the UCI data, asymptomatic patients are the highest-risk group because they were referred after abnormal tests. A public tool built on it would give worse scores to people with no symptoms, so the app offers a risk-factor review instead of a model estimate when there is no chest discomfort.

## 5. Unified architecture

    React SPA (Vite, TypeScript, React Router, TanStack Query, Recharts)
            |  JSON over HTTPS, Bearer JWT
    nginx  ->  FastAPI
                 routers        public, auth, patient, clinician, admin, research
                 core           security, crypto, rate limit, audit, deps, logging
                 services       triage, assessments, registry, reports
                 engine         inference, explanations, bands (loads artifacts)
                 research       metrics, validation engine, dataset validation, jobs
                 db             SQLAlchemy models, Alembic migrations
                 |
            PostgreSQL            model artifacts on disk (joblib + model card)

Safety layering for a symptom assessment: emergency flags and rules produce the triage level first. The research model can only raise it (`higher(triage, band)`), and its band is raised again by safety floors. The stored result keeps each layer separately with its provenance.

## 6. Directory structure

    backend/app/
      main.py                  application factory, middleware, static serving
      config.py                environment settings
      core/                    security, crypto, ratelimit, audit, deps, logging
      db/                      base, models
      routers/                 public, auth, patient, clinician, admin, research, common
      services/                triage, assessments, registry, reports
      research/                metrics, engine, paper, datasets, jobs
      engine.py  training.py  features.py  data.py  recalibration.py  wellness.py  schemas.py  seed.py
    backend/migrations/        Alembic
    backend/tests/
    frontend/src/
      api/  auth/  components/  pages/{public,patient,clinic,research}/  test/
    docs/  docker-compose.yml  .github/workflows/ci.yml

## 7. Database design

users(role, clinic_id, lockout fields) - clinics(code) - patient_profiles(user_id) - assessments(patient_id, kind, urgency, inputs JSON, result JSON, model_version, review fields, encrypted summary) - measurements - clinical_notes(encrypted body) - appointments - reports(sha256 of generated file) - model_versions(tag, card JSON, is_active) - clinic_calibrations - datasets(owner, columns JSON, sha256) - experiments(config, result JSON, provenance, progress) - audit_events(actor, clinic, action, entity).

Isolation: a clinician reaches a patient only when `patient.clinic_id == clinician.clinic_id`. The patient sets that link by entering the clinic code and can remove it, which ends access immediately. Researchers have no route to patient tables. Experiments and datasets are owner-only.

## 8. API design

All routes are under `/api`. Public: `health`, `health/ready`, `model-card`, `public/assess`, `public/wellness`. Auth: `register`, `register-clinic`, `login`, `me`, `join-clinic`, `leave-clinic`. Patient (`/me`): profile, dashboard, assessments (symptom, wellness, list, detail, report.pdf), measurements, appointments, clinicians, CSV exports. Clinic (`/clinic`): patients, queue, patient detail, review, notes, appointments, reports, exports, calibration. Admin (`/admin`): users, audit. Research (`/research`): models, uci-status, datasets, experiments, experiment report.pdf and report.csv. OpenAPI is served at `/api/docs`.

## 9. Roadmap as executed

1. Inspect both codebases, run their tests. 2. Foundation: configuration, database, migrations, security. 3. Patient and clinical workflows. 4. Research engine extraction and background jobs. 5. Dashboards and reports. 6. Tests: backend, frontend, end-to-end workflow, migrations. 7. Docker Compose, CI and documentation.

## 10. Risks and dependencies

- The real UCI files must be reachable at training time; the app labels any synthetic build.
- Rate limiting and the experiment slot are in-process and need Redis or a worker queue to scale horizontally.
- Tokens live in localStorage, which is exposed to cross-site scripting. A strict Content-Security-Policy is set, and httpOnly cookies with CSRF protection are the next hardening step.
- The research model is historical and unvalidated for current populations. Any real clinical use needs prospective validation and regulatory review.
