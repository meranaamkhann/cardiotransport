import io
import subprocess
import sys
from pathlib import Path

from app import data
from conftest import PASSWORD, email, headers
from test_patient import SYMPTOM


def test_complete_platform_workflow(client):
    admin_email = email("flow-admin")
    admin = client.post("/api/auth/register-clinic", json={"clinic_name": "Workflow Clinic", "email": admin_email, "password": PASSWORD, "full_name": "Flow Admin"}).json()
    code = admin["user"]["clinic"]["code"]
    a = headers(admin["access_token"])
    staff = {}
    for role in ("clinician", "researcher"):
        e = email(f"flow-{role}")
        assert client.post("/api/admin/users", headers=a, json={"email": e, "password": PASSWORD, "full_name": f"Flow {role}", "role": role}).status_code == 201
        staff[role] = headers(client.post("/api/auth/login", json={"email": e, "password": PASSWORD}).json()["access_token"])

    patient_email = email("flow-patient")
    registered = client.post("/api/auth/register", json={"email": patient_email, "password": PASSWORD, "full_name": "Flow Patient", "clinic_code": code})
    assert registered.status_code == 201
    p = headers(client.post("/api/auth/login", json={"email": patient_email, "password": PASSWORD}).json()["access_token"])
    assert client.put("/api/me/profile", headers=p, json={"sex": "female", "birth_year": 1972, "smoking": "never", "height_cm": 165}).status_code == 200

    assert client.post("/api/me/measurements", headers=p, json={"kind": "systolic", "value": 142}).status_code == 201
    made = client.post("/api/me/assessments/symptom", headers=p, json=SYMPTOM)
    assert made.status_code == 201
    assessment_id = made.json()["id"]
    history = client.get("/api/me/assessments", headers=p).json()
    assert [h["id"] for h in history] == [assessment_id]

    queue = client.get("/api/clinic/queue", headers=staff["clinician"]).json()
    assert queue[0]["id"] == assessment_id
    review = client.post(f"/api/clinic/assessments/{assessment_id}/review", headers=staff["clinician"], json={"summary": "Reviewed. Refer for stress ECG."})
    assert review.json()["status"] == "reviewed"
    assert client.get(f"/api/me/assessments/{assessment_id}", headers=p).json()["clinician_summary"].startswith("Reviewed")

    frame, _, _ = data.load_cohorts(force_synthetic=True)
    buffer = io.BytesIO(frame[["age", "sex", "cp", "trestbps", "chol", "thalach", "oldpeak", "num", "site"]].to_csv(index=False).encode())
    r = staff["researcher"]
    dataset = client.post("/api/research/datasets", headers=r, data={"name": "Workflow data"}, files={"file": ("w.csv", buffer, "text/csv")}).json()
    config = {"name": "Workflow validation", "kind": "custom_validation", "dataset_id": dataset["id"], "target_column": "num", "site_column": "site",
              "dev_site": "Cleveland", "feature_columns": ["age", "sex", "cp", "trestbps", "chol", "thalach", "oldpeak"], "bootstrap": 100, "repeats": 1}
    experiment = client.post("/api/research/experiments", headers=r, json=config).json()
    result = client.get(f"/api/research/experiments/{experiment['id']}", headers=r).json()
    assert result["status"] == "completed", result["error"]
    portable = result["result"]["models"]["portable_logistic"]
    assert portable["external"]["Hungary"]["cal_slope"] is not None
    assert result["result"]["recalibration"]["portable_logistic"]["Switzerland"]["full_update"]

    assert client.get(f"/api/clinic/assessments/{assessment_id}/report.pdf", headers=staff["clinician"]).content.startswith(b"%PDF")
    assert client.get(f"/api/research/experiments/{experiment['id']}/report.pdf", headers=r).content.startswith(b"%PDF")
    audit = {e["action"] for e in client.get("/api/admin/audit", headers=a).json()}
    assert {"register", "assessment_created", "assessment_reviewed", "report_generated"} <= audit


def test_migrations_apply_cleanly(tmp_path):
    root = Path(__file__).resolve().parent.parent
    env = {"DATABASE_URL": f"sqlite:///{tmp_path}/migrated.db", "PATH": "/usr/bin:/usr/local/bin", "CARDIOLENS_ENV": "test"}
    up = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, capture_output=True, text=True)
    assert up.returncode == 0, up.stderr
    down = subprocess.run([sys.executable, "-m", "alembic", "downgrade", "base"], cwd=root, env=env, capture_output=True, text=True)
    assert down.returncode == 0, down.stderr
