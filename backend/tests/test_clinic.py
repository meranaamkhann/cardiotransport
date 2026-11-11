from conftest import headers, register_patient
from test_patient import SYMPTOM


def test_clinician_sees_only_own_clinic(client, clinic):
    mine = register_patient(client, clinic["code"])
    other = client.post("/api/auth/register-clinic", json={"clinic_name": "Other Clinic", "email": "other.admin@example.org",
                                                           "password": "Str0ngPassw0rd", "full_name": "Olive Other"})
    other_code = other.json()["user"]["clinic"]["code"] if other.status_code == 201 else None
    if other_code is None:
        other = client.post("/api/auth/login", json={"email": "other.admin@example.org", "password": "Str0ngPassw0rd"}).json()
        other_code = other["user"]["clinic"]["code"]
    outsider = register_patient(client, other_code)
    c = headers(clinic["clinician"]["access_token"])
    ids = {p["id"] for p in client.get("/api/clinic/patients", headers=c).json()}
    assert mine["user"]["id"] in ids and outsider["user"]["id"] not in ids
    assert client.get(f"/api/clinic/patients/{outsider['user']['id']}", headers=c).status_code == 404


def test_unaffiliated_patient_is_invisible(client, clinic):
    solo = register_patient(client)
    made = client.post("/api/me/assessments/symptom", headers=headers(solo["access_token"]), json=SYMPTOM).json()
    c = headers(clinic["clinician"]["access_token"])
    assert client.get(f"/api/clinic/patients/{solo['user']['id']}", headers=c).status_code == 404
    assert client.post(f"/api/clinic/assessments/{made['id']}/review", headers=c, json={"summary": "Looks fine"}).status_code == 404


def test_withdrawing_consent_removes_access(client, clinic):
    member = register_patient(client, clinic["code"])
    c = headers(clinic["clinician"]["access_token"])
    assert client.get(f"/api/clinic/patients/{member['user']['id']}", headers=c).status_code == 200
    client.post("/api/auth/leave-clinic", headers=headers(member["access_token"]))
    assert client.get(f"/api/clinic/patients/{member['user']['id']}", headers=c).status_code == 404


def test_review_notes_and_report(client, clinic, patient):
    p, c = headers(patient["access_token"]), headers(clinic["clinician"]["access_token"])
    made = client.post("/api/me/assessments/symptom", headers=p, json=SYMPTOM).json()
    queue = client.get("/api/clinic/queue", headers=c).json()
    assert any(q["id"] == made["id"] for q in queue)
    reviewed = client.post(f"/api/clinic/assessments/{made['id']}/review", headers=c, json={"summary": "Exertional symptoms; arrange ECG and stress test."})
    assert reviewed.json()["status"] == "reviewed"
    assert reviewed.json()["clinician_summary"].startswith("Exertional")
    assert not any(q["id"] == made["id"] for q in client.get("/api/clinic/queue", headers=c).json())
    seen = client.get(f"/api/me/assessments/{made['id']}", headers=p).json()
    assert seen["status"] == "reviewed" and seen["reviewer"]
    note = client.post(f"/api/clinic/patients/{patient['user']['id']}/notes", headers=c, json={"body": "Discussed lifestyle changes.", "assessment_id": made["id"]})
    assert note.status_code == 201
    detail = client.get(f"/api/clinic/patients/{patient['user']['id']}", headers=c).json()
    assert detail["notes"][0]["body"] == "Discussed lifestyle changes."
    assert client.get(f"/api/clinic/assessments/{made['id']}/report.pdf", headers=c).content.startswith(b"%PDF")
    assert client.get(f"/api/clinic/patients/{patient['user']['id']}/export/assessments.csv", headers=c).status_code == 200
    assert client.get(f"/api/me/assessments/{made['id']}/report.pdf", headers=p).status_code == 200


def test_notes_are_encrypted_at_rest(client, clinic, patient):
    from app.db.base import SessionLocal
    from app.db.models import ClinicalNote
    c = headers(clinic["clinician"]["access_token"])
    client.post(f"/api/clinic/patients/{patient['user']['id']}/notes", headers=c, json={"body": "Highly confidential observation"})
    with SessionLocal() as db:
        stored = db.query(ClinicalNote).order_by(ClinicalNote.id.desc()).first().body_encrypted
    assert "confidential" not in stored


def test_queue_orders_by_urgency(client, clinic):
    calm, sick = register_patient(client, clinic["code"]), register_patient(client, clinic["code"])
    calm_a = client.post("/api/me/assessments/symptom", headers=headers(calm["access_token"]),
                         json={**SYMPTOM, "chest_discomfort": "none", "discomfort_with_effort": False, "breathlessness": "none", "severity": 2, "fatigue": True}).json()
    sick_a = client.post("/api/me/assessments/symptom", headers=headers(sick["access_token"]), json={**SYMPTOM, "emergency": ["fainting"]}).json()
    queue = client.get("/api/clinic/queue", headers=headers(clinic["clinician"]["access_token"])).json()
    ids = [q["id"] for q in queue]
    assert ids.index(sick_a["id"]) < ids.index(calm_a["id"])


def test_clinician_schedules_and_updates_appointment(client, clinic, patient):
    c = headers(clinic["clinician"]["access_token"])
    r = client.post(f"/api/clinic/patients/{patient['user']['id']}/appointments", headers=c, json={"scheduled_at": "2999-06-01T09:00:00Z", "reason": "ECG and stress test"})
    assert r.status_code == 201 and r.json()["status"] == "confirmed"
    done = client.patch(f"/api/clinic/appointments/{r.json()['id']}", headers=c, json={"status": "completed"})
    assert done.json()["status"] == "completed"


def test_clinic_calibration_applies_to_member_assessments(client, clinic, patient):
    from app import data
    from app.recalibration import CLINICAL
    frame, _, _ = data.load_cohorts(force_synthetic=True)
    local = frame[frame["site"] == "Switzerland"].copy()
    local["outcome"] = local["target"]
    csv = local[CLINICAL + ["outcome"]].to_csv(index=False)
    c = headers(clinic["clinician"]["access_token"])
    preview = client.post("/api/clinic/calibration", headers=c, files={"file": ("local.csv", csv, "text/csv")}, data={"apply": "false"})
    assert preview.status_code == 200 and preview.json()["applied"] is False
    assert client.get("/api/clinic/calibration", headers=c).json() == []
    applied = client.post("/api/clinic/calibration", headers=c, files={"file": ("local.csv", csv, "text/csv")}, data={"apply": "true"})
    assert applied.json()["applied"] is True
    assert client.get("/api/clinic/calibration", headers=c).json()
    body = client.post("/api/me/assessments/symptom", headers=headers(patient["access_token"]), json=SYMPTOM).json()
    assert body["result"]["model"]["local"]["probability"] > 0


def test_calibration_rejects_bad_files(client, clinic):
    c = headers(clinic["clinician"]["access_token"])
    small = "age,sex,cp,exang,trestbps,chol,fbs,outcome\n50,1,4,1,130,200,0,1\n"
    assert client.post("/api/clinic/calibration", headers=c, files={"file": ("x.csv", small, "text/csv")}).status_code == 422
    assert client.post("/api/clinic/calibration", headers=c, files={"file": ("x.csv", "age,sex\n1,2\n", "text/csv")}).status_code == 422
