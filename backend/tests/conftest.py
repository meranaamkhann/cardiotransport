import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "CARDIOLENS_UPLOADS": f"{_tmp}/uploads",
    "CARDIOLENS_DATA": f"{_tmp}/data",
    "CARDIOLENS_ARTIFACTS": f"{_tmp}/artifacts",
    "RATE_LIMIT_ENABLED": "0",
    "CARDIOLENS_ENV": "test",
    "SECRET_KEY": "test-secret-key-for-the-suite",
})

import itertools

import pytest
from fastapi.testclient import TestClient

from app import data
from app.config import get_settings
from app.core import ratelimit
from app.main import create_app
from app.training import train

counter = itertools.count(1)
PASSWORD = "Str0ngPassw0rd"


@pytest.fixture(scope="session")
def client():
    settings = get_settings()
    frame, source, quality = data.load_cohorts(force_synthetic=True)
    train(frame, source, quality, out_dir=settings.artifact_dir, run_paper=False)
    with TestClient(create_app(settings.artifact_dir, settings.artifact_dir / "none", create_tables=True)) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_limits():
    ratelimit.reset()


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def email(prefix):
    return f"{prefix}{next(counter)}@example.org"


@pytest.fixture
def clinic(client):
    admin_email = email("admin")
    r = client.post("/api/auth/register-clinic", json={"clinic_name": "Test Heart Clinic", "email": admin_email,
                                                       "password": PASSWORD, "full_name": "Ada Admin"})
    assert r.status_code == 201, r.text
    admin = r.json()
    code = admin["user"]["clinic"]["code"]
    staff = {}
    for role in ("clinician", "researcher"):
        e = email(role)
        r = client.post("/api/admin/users", headers=headers(admin["access_token"]),
                        json={"email": e, "password": PASSWORD, "full_name": f"Test {role}", "role": role})
        assert r.status_code == 201, r.text
        staff[role] = client.post("/api/auth/login", json={"email": e, "password": PASSWORD}).json()
    return {"code": code, "admin": admin, "clinician": staff["clinician"], "researcher": staff["researcher"]}


def register_patient(client, code=None, complete=True):
    e = email("patient")
    body = {"email": e, "password": PASSWORD, "full_name": "Pat Ient"}
    if code:
        body["clinic_code"] = code
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    auth = r.json()
    if complete:
        r = client.put("/api/me/profile", headers=headers(auth["access_token"]),
                       json={"sex": "male", "birth_year": 1968, "height_cm": 172, "smoking": "former"})
        assert r.status_code == 200, r.text
    return auth


@pytest.fixture
def patient(client, clinic):
    return register_patient(client, clinic["code"])
