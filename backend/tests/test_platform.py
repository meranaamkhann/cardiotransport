import io
import itertools

import pytest

from app import research_demo

counter = itertools.count()
BASE = dict(pathway="symptomatic", age=58, sex="male", chest_pain="typical", exercise_pain=True, emergency=[])


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def signup(client, clinic="northside"):
    email = f"user{next(counter)}@example.org"
    r = client.post("/api/auth/register", json={"email": email, "name": "Pat Example", "password": "LongPassword123", "clinic": clinic})
    assert r.status_code == 201
    return email, r.json()["access_token"]


def staff(client, role, clinic="northside"):
    admin = client.post("/api/auth/login", json={"email": "admin@clinic.org", "password": "AdminPass12345"}).json()["access_token"]
    email = f"{role}{next(counter)}@example.org"
    r = client.post("/api/admin/users", headers=headers(admin), json={"email": email, "name": role.title(), "password": "StaffPassword123", "clinic": clinic, "role": role})
    assert r.status_code == 201
    return client.post("/api/auth/login", json={"email": email, "password": "StaffPassword123"}).json()["access_token"]


def test_register_login_me_and_duplicates(client):
    email, token = signup(client)
    assert client.get("/api/auth/me", headers=headers(token)).json()["role"] == "patient"
    assert client.post("/api/auth/register", json={"email": email, "name": "x", "password": "LongPassword123"}).status_code == 409
    assert client.post("/api/auth/register", json={"email": "a@b.co", "name": "x", "password": "short"}).status_code == 422
    assert client.post("/api/auth/login", json={"email": email, "password": "wrong-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": email, "password": "LongPassword123"}).status_code == 200


def test_public_registration_cannot_choose_role(client):
    r = client.post("/api/auth/register", json={"email": "sneaky@example.org", "name": "S", "password": "LongPassword123", "role": "admin"})
    assert r.json()["role"] == "patient"


def test_authentication_and_role_enforced(client):
    assert client.get("/api/patient/assessments").status_code == 401
    assert client.get("/api/patient/assessments", headers=headers("garbage")).status_code == 401
    _, patient = signup(client)
    assert client.get("/api/clinic/patients", headers=headers(patient)).status_code == 403
    assert client.post("/api/admin/users", headers=headers(patient), json={}).status_code == 403
    assert client.post("/api/research/experiments/demo", headers=headers(patient)).status_code == 403


def test_patient_flow_and_isolation(client):
    _, one = signup(client)
    _, two = signup(client)
    r = client.post("/api/patient/assessments/symptom", headers=headers(one), json={**BASE, "emergency": ["fainting"]})
    assert r.status_code == 201 and r.json()["emergency"] is True and r.json()["band"] == "higher"
    aid = r.json()["id"]
    assert [a["id"] for a in client.get("/api/patient/assessments", headers=headers(one)).json()] == [aid]
    assert client.get(f"/api/patient/assessments/{aid}", headers=headers(two)).status_code == 404
    assert client.get("/api/patient/assessments", headers=headers(two)).json() == []
    w = client.post("/api/patient/assessments/wellness", headers=headers(one), json={"age": 50, "sex": "female", "smoking": "never"})
    assert w.status_code == 201
    csv = client.get("/api/patient/export.csv", headers=headers(one))
    assert csv.status_code == 200 and csv.text.count("\n") == 3


def test_invalid_assessment_rejected(client):
    _, token = signup(client)
    assert client.post("/api/patient/assessments/symptom", headers=headers(token), json={**BASE, "age": 5}).status_code == 422
    assert client.post("/api/patient/assessments/symptom", headers=headers(token), json={**BASE, "chest_pain": "none"}).status_code == 422


def test_clinical_review_scoped_to_clinic(client):
    email, patient = signup(client, "northside")
    aid = client.post("/api/patient/assessments/symptom", headers=headers(patient), json=BASE).json()["id"]
    doctor, outsider = staff(client, "clinician"), staff(client, "clinician", "southside")
    directory = client.get("/api/clinic/patients", headers=headers(doctor)).json()
    pid = next(p["id"] for p in directory if p["email"] == email)
    assert next(p for p in directory if p["id"] == pid)["pending_review"] == 1
    assert all(p["email"] != email for p in client.get("/api/clinic/patients", headers=headers(outsider)).json())
    assert client.get(f"/api/clinic/patients/{pid}/assessments", headers=headers(outsider)).status_code == 404
    assert client.post(f"/api/clinic/assessments/{aid}/notes", headers=headers(outsider), json={"body": "x"}).status_code == 404
    done = client.post(f"/api/clinic/assessments/{aid}/notes", headers=headers(doctor), json={"body": "Book an ECG."})
    assert done.status_code == 201 and done.json()["status"] == "reviewed"
    seen = client.get(f"/api/patient/assessments/{aid}", headers=headers(patient)).json()
    assert seen["notes"][0]["source"] == "clinician_reviewed" and seen["provenance"]["assessment"] == "model_generated"


def test_clinicians_need_a_clinic(client):
    admin = client.post("/api/auth/login", json={"email": "admin@clinic.org", "password": "AdminPass12345"}).json()["access_token"]
    r = client.post("/api/admin/users", headers=headers(admin), json={"email": "r@example.org", "name": "R", "password": "StaffPassword123", "role": "researcher"})
    assert r.status_code == 201


def test_login_rate_limit(client):
    statuses = [client.post("/api/auth/login", json={"email": "limit@example.org", "password": "nope-nope-nope"}).status_code for _ in range(12)]
    assert 429 in statuses


def small_csv():
    frame, cfg = research_demo.synthetic()
    return frame.groupby("site").head(120).to_csv(index=False).encode(), cfg


def test_research_upload_and_isolation(client):
    researcher, other = staff(client, "researcher"), staff(client, "researcher")
    raw, cfg = small_csv()
    form = dict(name="My study", target="outcome", site_col="site", dev_site="Hospital A", group_col="sex")
    r = client.post("/api/research/experiments", headers=headers(researcher), data=form, files={"file": ("d.csv", io.BytesIO(raw))})
    assert r.status_code == 201 and r.json()["origin"] == "uploaded"
    eid = r.json()["id"]
    body = client.get(f"/api/research/experiments/{eid}", headers=headers(researcher)).json()
    assert "logistic_portable" in body["result"]["external"] and body["result"]["provenance"]["origin"] == "uploaded"
    assert client.get(f"/api/research/experiments/{eid}", headers=headers(other)).status_code == 404
    assert [e["id"] for e in client.get("/api/research/experiments", headers=headers(researcher)).json()] == [eid]


def test_research_validation(client):
    researcher = staff(client, "researcher")
    raw, _ = small_csv()
    bad = dict(name="x", target="age", site_col="site", dev_site="Hospital A")
    assert client.post("/api/research/experiments", headers=headers(researcher), data=bad, files={"file": ("d.csv", io.BytesIO(raw))}).status_code == 422
    junk = dict(name="x", target="outcome", site_col="site", dev_site="Hospital A")
    assert client.post("/api/research/experiments", headers=headers(researcher), data=junk, files={"file": ("d.csv", io.BytesIO(b"a,b\n1,2\n"))}).status_code == 422
    missing = dict(name="x", target="outcome", site_col="site", dev_site="Nowhere")
    assert client.post("/api/research/experiments", headers=headers(researcher), data=missing, files={"file": ("d.csv", io.BytesIO(raw))}).status_code == 422


def test_demo_is_labelled_synthetic_and_paper_results_available(client):
    researcher = staff(client, "researcher")
    r = client.post("/api/research/experiments/demo", headers=headers(researcher))
    assert r.status_code == 201 and r.json()["origin"] == "synthetic_demo"
    note = client.get(f"/api/research/experiments/{r.json()['id']}", headers=headers(researcher)).json()["result"]["provenance"]["note"]
    assert "Synthetic" in note
    paper = client.get("/api/research/paper-results", headers=headers(researcher))
    assert paper.status_code == 200 and paper.json()["provenance"] in ("synthetic_demo", "reproduced_from_supplied_data")


def test_health_reports_database(client):
    assert client.get("/api/health").json()["database"] == "ok"
