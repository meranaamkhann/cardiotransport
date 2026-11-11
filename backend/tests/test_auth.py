import pytest

from app.config import get_settings
from conftest import PASSWORD, email, headers, register_patient


def test_register_login_me(client):
    auth = register_patient(client, complete=False)
    assert auth["user"]["role"] == "patient"
    login = client.post("/api/auth/login", json={"email": auth["user"]["email"], "password": PASSWORD})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers=headers(login.json()["access_token"]))
    assert me.json()["email"] == auth["user"]["email"]
    assert me.json()["profile_complete"] is False


def test_password_rules(client):
    short = client.post("/api/auth/register", json={"email": email("x"), "password": "short1", "full_name": "Short Pw"})
    letters = client.post("/api/auth/register", json={"email": email("x"), "password": "onlylettersonly", "full_name": "Only Letters"})
    assert short.status_code == 422 and letters.status_code == 422


def test_duplicate_email(client):
    auth = register_patient(client, complete=False)
    again = client.post("/api/auth/register", json={"email": auth["user"]["email"].upper(), "password": PASSWORD, "full_name": "Dup Licate"})
    assert again.status_code == 409


def test_wrong_password_and_lockout(client):
    auth = register_patient(client, complete=False)
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": auth["user"]["email"], "password": "wrongpassword1"}).status_code == 401
    locked = client.post("/api/auth/login", json={"email": auth["user"]["email"], "password": PASSWORD})
    assert locked.status_code == 423


def test_requires_token(client):
    assert client.get("/api/me/dashboard").status_code == 401
    assert client.get("/api/me/dashboard", headers=headers("not-a-token")).status_code == 401


def test_rate_limit_on_login(client):
    settings = get_settings()
    settings.rate_limit_enabled = True
    try:
        codes = [client.post("/api/auth/login", json={"email": "nobody@example.org", "password": "whateverpass1"}).status_code for _ in range(17)]
    finally:
        settings.rate_limit_enabled = False
    assert 429 in codes


def test_role_enforcement(client, clinic, patient):
    p = headers(patient["access_token"])
    assert client.get("/api/clinic/patients", headers=p).status_code == 403
    assert client.get("/api/research/models", headers=p).status_code == 403
    assert client.get("/api/admin/users", headers=p).status_code == 403
    c = headers(clinic["clinician"]["access_token"])
    assert client.get("/api/me/dashboard", headers=c).status_code == 403
    assert client.get("/api/research/models", headers=c).status_code == 403
    assert client.get("/api/admin/users", headers=c).status_code == 403
    r = headers(clinic["researcher"]["access_token"])
    assert client.get("/api/clinic/patients", headers=r).status_code == 403


def test_admin_manages_staff(client, clinic):
    a = headers(clinic["admin"]["access_token"])
    users = client.get("/api/admin/users", headers=a).json()
    assert {u["role"] for u in users} >= {"clinic_admin", "clinician", "researcher"}
    target = next(u for u in users if u["role"] == "clinician")
    assert client.patch(f"/api/admin/users/{target['id']}/active", params={"active": False}, headers=a).status_code == 200
    blocked = client.post("/api/auth/login", json={"email": target["email"], "password": PASSWORD})
    assert blocked.status_code == 401
    me = next(u for u in users if u["role"] == "clinic_admin")
    assert client.patch(f"/api/admin/users/{me['id']}/active", params={"active": False}, headers=a).status_code == 422
    assert any(e["action"] == "staff_deactivated" for e in client.get("/api/admin/audit", headers=a).json())


def test_join_and_leave_clinic(client, clinic):
    auth = register_patient(client)
    h = headers(auth["access_token"])
    assert client.post("/api/auth/join-clinic", headers=h, json={"code": "ZZZZZZ"}).status_code == 404
    joined = client.post("/api/auth/join-clinic", headers=h, json={"code": clinic["code"].lower()})
    assert joined.json()["clinic"]["name"] == "Test Heart Clinic"
    assert joined.json()["clinic"]["code"] is None
    left = client.post("/api/auth/leave-clinic", headers=h)
    assert left.json()["clinic"] is None


@pytest.mark.parametrize("path", ["/api/health", "/api/health/ready"])
def test_health(client, path):
    assert client.get(path).status_code == 200


def test_security_headers(client):
    assert client.get("/api/health").headers["x-content-type-options"] == "nosniff"
