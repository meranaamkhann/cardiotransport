from conftest import headers, register_patient

SYMPTOM = {"chest_discomfort": "typical", "discomfort_with_effort": True, "breathlessness": "on_exertion", "palpitations": False,
           "dizziness": False, "fatigue": True, "duration": "weeks", "severity": 5, "emergency": [], "conditions": ["hypertension"],
           "systolic": 148, "cholesterol": 232, "fasting_glucose": 104}


def test_incomplete_profile_blocks_assessment(client):
    auth = register_patient(client, complete=False)
    r = client.post("/api/me/assessments/symptom", headers=headers(auth["access_token"]), json=SYMPTOM)
    assert r.status_code == 422
    assert "profile" in r.json()["detail"].lower()


def test_symptom_assessment_flow(client, patient):
    h = headers(patient["access_token"])
    r = client.post("/api/me/assessments/symptom", headers=h, json=SYMPTOM)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "symptom"
    assert body["result"]["model"]["tier"] in ("core", "clinical")
    assert body["result"]["triage"]["level"] in ("prompt", "urgent", "emergency")
    assert body["inputs"]["age"] > 18
    listed = client.get("/api/me/assessments", headers=h).json()
    assert listed[0]["id"] == body["id"]
    assert client.get(f"/api/me/assessments/{body['id']}", headers=h).json()["status"] == "submitted"


def test_emergency_overrides_everything(client, patient):
    h = headers(patient["access_token"])
    quiet = {**SYMPTOM, "chest_discomfort": "non_anginal", "discomfort_with_effort": False, "severity": 2,
             "emergency": ["pain_at_rest"], "systolic": 110, "cholesterol": 150}
    body = client.post("/api/me/assessments/symptom", headers=h, json=quiet).json()
    assert body["urgency"] == "emergency"
    assert body["result"]["model"]["emergency"]["active"] is True


def test_low_model_score_cannot_lower_triage(client, patient):
    h = headers(patient["access_token"])
    payload = {**SYMPTOM, "chest_discomfort": "typical", "severity": 9, "duration": "minutes", "systolic": 105, "cholesterol": 150}
    assert client.post("/api/me/assessments/symptom", headers=h, json=payload).json()["urgency"] == "emergency"


def test_no_chest_pain_skips_model(client, patient):
    h = headers(patient["access_token"])
    payload = {**SYMPTOM, "chest_discomfort": "none", "discomfort_with_effort": False, "breathlessness": "none", "severity": 2}
    body = client.post("/api/me/assessments/symptom", headers=h, json=payload).json()
    assert body["result"]["model"] is None
    assert body["result"]["model_note"]


def test_measurements_crud_and_autofill(client, patient):
    h = headers(patient["access_token"])
    assert client.post("/api/me/measurements", headers=h, json={"kind": "systolic", "value": 999}).status_code == 422
    assert client.post("/api/me/measurements", headers=h, json={"kind": "systolic", "value": 151}).status_code == 201
    created = client.post("/api/me/measurements", headers=h, json={"kind": "cholesterol", "value": 260}).json()
    assert client.get("/api/me/measurements", headers=h, params={"kind": "cholesterol"}).json()[0]["id"] == created["id"]
    payload = {**SYMPTOM, "systolic": None, "cholesterol": None}
    body = client.post("/api/me/assessments/symptom", headers=h, json=payload).json()
    assert set(body["inputs"]["autofilled_from_history"]) >= {"systolic", "cholesterol"}
    assert client.delete(f"/api/me/measurements/{created['id']}", headers=h).status_code == 204
    assert client.delete(f"/api/me/measurements/{created['id']}", headers=h).status_code == 404


def test_future_measurement_rejected(client, patient):
    h = headers(patient["access_token"])
    r = client.post("/api/me/measurements", headers=h, json={"kind": "weight", "value": 70, "measured_at": "2999-01-01T00:00:00Z"})
    assert r.status_code == 422


def test_wellness_assessment_saves_measurements(client, patient):
    h = headers(patient["access_token"])
    payload = {"systolic": 128, "diastolic": 82, "cholesterol": 215, "fasting_glucose": 99, "weight_kg": 74, "activity_minutes": 90}
    r = client.post("/api/me/assessments/wellness", headers=h, json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["result"]["provenance"]["assessment"].startswith("guideline")
    kinds = {m["kind"] for m in client.get("/api/me/measurements", headers=h).json()}
    assert {"systolic", "diastolic", "cholesterol", "glucose", "weight"} <= kinds


def test_patient_cannot_read_other_patients_data(client, clinic):
    first, second = register_patient(client, clinic["code"]), register_patient(client, clinic["code"])
    made = client.post("/api/me/assessments/symptom", headers=headers(first["access_token"]), json=SYMPTOM).json()
    other = headers(second["access_token"])
    assert client.get(f"/api/me/assessments/{made['id']}", headers=other).status_code == 404
    assert client.get(f"/api/me/assessments/{made['id']}/report.pdf", headers=other).status_code == 404


def test_report_and_exports(client, patient):
    h = headers(patient["access_token"])
    made = client.post("/api/me/assessments/symptom", headers=h, json=SYMPTOM).json()
    pdf = client.get(f"/api/me/assessments/{made['id']}/report.pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get("/api/me/export/assessments.csv", headers=h).text.startswith("created_at,kind")
    assert client.get("/api/me/export/measurements.csv", headers=h).status_code == 200


def test_appointments(client, clinic):
    solo = register_patient(client)
    h = headers(solo["access_token"])
    future = "2999-05-01T10:00:00Z"
    assert client.post("/api/me/appointments", headers=h, json={"scheduled_at": future, "reason": "Check-up"}).status_code == 422
    member = register_patient(client, clinic["code"])
    mh = headers(member["access_token"])
    assert client.post("/api/me/appointments", headers=mh, json={"scheduled_at": "2000-01-01T10:00:00Z", "reason": "Too late"}).status_code == 422
    made = client.post("/api/me/appointments", headers=mh, json={"scheduled_at": future, "reason": "Blood pressure review"})
    assert made.status_code == 201
    assert client.patch(f"/api/me/appointments/{made.json()['id']}", headers=mh, json={"status": "confirmed"}).status_code == 403
    assert client.patch(f"/api/me/appointments/{made.json()['id']}", headers=mh, json={"status": "cancelled"}).json()["status"] == "cancelled"


def test_dashboard(client, patient):
    h = headers(patient["access_token"])
    client.post("/api/me/assessments/symptom", headers=h, json=SYMPTOM)
    d = client.get("/api/me/dashboard", headers=h).json()
    assert d["total_assessments"] == 1 and d["recent"] and d["user"]["profile_complete"] is True


def test_score_range_and_second_opinion(client, patient):
    body = client.post("/api/me/assessments/symptom", headers=headers(patient["access_token"]), json=SYMPTOM).json()
    model = body["result"]["model"]
    low, high = model["score_range"]
    assert 0 <= low <= model["model_score"] <= high <= 100 or low <= high
    assert model["second_opinion"]["band"] in ("lower", "moderate", "higher")
    assert isinstance(model["second_opinion"]["agrees"], bool)


def test_card_reports_second_opinion_agreement(client):
    tier = client.get("/api/model-card").json()["deployment"]["clinical"]
    assert tier["bootstrap_models"] >= 100
    assert 0 <= tier["agreement"]["same_band_pct"] <= 100
    assert set(tier["forest_held_out_site"]) == set(tier["held_out_site"])


def test_export_and_access_log(client, clinic, patient):
    p = headers(patient["access_token"])
    client.post("/api/me/assessments/symptom", headers=p, json=SYMPTOM)
    client.get(f"/api/clinic/patients/{patient['user']['id']}", headers=headers(clinic["clinician"]["access_token"]))
    exported = client.get("/api/me/export.json", headers=p)
    assert exported.status_code == 200
    data = exported.json()
    assert len(data["assessments"]) == 1 and data["profile"]["sex"] == "male"
    log = client.get("/api/me/access-log", headers=p).json()
    assert log and log[0]["action"] == "patient record viewed" and log[0]["who"]


def test_delete_account_removes_everything(client, clinic):
    auth = register_patient(client, clinic["code"])
    p = headers(auth["access_token"])
    client.post("/api/me/assessments/symptom", headers=p, json=SYMPTOM)
    client.post("/api/me/measurements", headers=p, json={"kind": "weight", "value": 70})
    c = headers(clinic["clinician"]["access_token"])
    client.post(f"/api/clinic/patients/{auth['user']['id']}/notes", headers=c, json={"body": "A note"})
    assert client.post("/api/me/delete-account", headers=p, json={"password": "wrong-password1"}).status_code == 403
    assert client.post("/api/me/delete-account", headers=p, json={"password": "Str0ngPassw0rd"}).status_code == 204
    assert client.get("/api/auth/me", headers=p).status_code == 401
    assert client.post("/api/auth/login", json={"email": auth["user"]["email"], "password": "Str0ngPassw0rd"}).status_code == 401
    assert client.get(f"/api/clinic/patients/{auth['user']['id']}", headers=c).status_code == 404
    from app.db.base import SessionLocal
    from app.db.models import Assessment, ClinicalNote, Measurement
    with SessionLocal() as db:
        for model in (Assessment, Measurement, ClinicalNote):
            assert db.query(model).filter(model.patient_id == auth["user"]["id"]).count() == 0
