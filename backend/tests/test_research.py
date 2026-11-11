import io

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from app import data as data_module
from app.research import datasets, metrics as M
from app.services.reports import csv_safe
from conftest import headers

FAST = {"bootstrap": 100, "repeats": 1}


def upload_csv(frame):
    return io.BytesIO(frame.to_csv(index=False).encode())


@pytest.fixture
def multi_site_csv():
    frame, _, _ = data_module.load_cohorts(force_synthetic=True)
    out = frame[["age", "sex", "cp", "trestbps", "chol", "thalach", "oldpeak", "ca", "num", "site"]].copy()
    out["gender_group"] = out["sex"].map({0.0: "F", 1.0: "M"})
    return out


def wait_for(client, researcher, experiment_id):
    r = client.get(f"/api/research/experiments/{experiment_id}", headers=headers(researcher["access_token"]))
    assert r.status_code == 200
    return r.json()


def test_fast_auc_matches_sklearn():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 400)
    p = np.round(rng.random(400), 2)
    assert abs(M.auc(y, p) - roc_auc_score(y, p)) < 1e-12


def test_metric_set_bootstrap_contains_estimate():
    rng = np.random.default_rng(5)
    y = rng.integers(0, 2, 300)
    p = np.clip(y * 0.3 + rng.random(300) * 0.7, 0, 1)
    m = M.metric_set(y, p, rng, 300)
    assert m["auc_ci"][0] <= m["auc"] <= m["auc_ci"][1]
    assert 0 <= m["balanced_accuracy"] <= 1 and m["average_precision"] is not None


def test_decision_curve_treat_all_formula():
    y = np.array([1] * 30 + [0] * 70)
    curve = M.decision_curve(y, np.full(100, 0.5), np.full(100, 0.5))
    t = curve["thresholds"][3]
    assert curve["treat_all"][3] == round(0.3 - 0.7 * t / (1 - t), 4)
    assert set(curve["treat_none"]) == {0.0}


def test_update_study_improves_shifted_site():
    rng = np.random.default_rng(9)
    z = rng.normal(0, 1.2, 600)
    y = (rng.random(600) < M.sig(z + 1.5)).astype(int)
    result = M.update_study(y, M.sig(z), rng, draws=40)
    assert result["80"]["intercept"] < result["80"]["none"]


def test_csv_safe_blocks_formulas():
    assert csv_safe("=SUM(A1)") == "'=SUM(A1)"
    assert csv_safe("normal") == "normal"


def test_upload_validation_rules():
    good = pd.DataFrame({"a": range(60), "b": range(60)})
    frame, info, _ = datasets.inspect_csv(good.to_csv(index=False).encode(), 1_000_000)
    assert len(frame) == 60 and {c["name"] for c in info} == {"a", "b"}
    with pytest.raises(ValueError):
        datasets.inspect_csv(good.head(10).to_csv(index=False).encode(), 1_000_000)
    with pytest.raises(ValueError):
        datasets.inspect_csv(good.assign(email="a@b.c").to_csv(index=False).encode(), 1_000_000)
    with pytest.raises(ValueError):
        datasets.inspect_csv(good.rename(columns={"a": "=cmd()"}).to_csv(index=False).encode(), 1_000_000)
    with pytest.raises(ValueError):
        datasets.inspect_csv(b"x" * 2_000, 1_000)


def test_upload_endpoint(client, clinic, multi_site_csv):
    r = headers(clinic["researcher"]["access_token"])
    ok = client.post("/api/research/datasets", headers=r, data={"name": "Synthetic multi-site"}, files={"file": ("d.csv", upload_csv(multi_site_csv), "text/csv")})
    assert ok.status_code == 201 and ok.json()["n_rows"] == len(multi_site_csv)
    bad_ext = client.post("/api/research/datasets", headers=r, data={"name": "Bad file"}, files={"file": ("d.exe", b"a,b\n1,2\n", "application/octet-stream")})
    assert bad_ext.status_code == 422
    assert any(d["id"] == ok.json()["id"] for d in client.get("/api/research/datasets", headers=r).json())
    assert client.delete(f"/api/research/datasets/{ok.json()['id']}", headers=r).status_code == 204


def test_paper_replication_on_synthetic(client, clinic):
    r = headers(clinic["researcher"]["access_token"])
    made = client.post("/api/research/experiments", headers=r, json={"name": "Synthetic replication", "kind": "paper_replication", "source": "synthetic", **FAST})
    assert made.status_code == 202
    exp = wait_for(client, clinic["researcher"], made.json()["id"])
    assert exp["status"] == "completed", exp["error"]
    assert exp["provenance"] == "synthetic_demo"
    result = exp["result"]
    assert set(result["models"]) == {"full_logistic", "portable_logistic", "full_forest", "portable_forest"}
    assert result["sites_external"] == ["Hungary", "Switzerland", "Long Beach VA"]
    assert result["cohorts"]["Cleveland"]["n"] == 303 and result["cohorts"]["Hungary"]["n"] == 294
    assert result["cohorts"]["Switzerland"]["n"] == 123 and result["cohorts"]["Long Beach VA"]["n"] == 200
    portable = result["models"]["portable_logistic"]
    assert len(portable["features"]) == 10 and len(result["models"]["full_logistic"]["features"]) == 13
    for key in ("roc", "calibration", "dca"):
        assert portable[key]
    assert result["recalibration"]["portable_logistic"]["Hungary"]["update_study"]
    assert result["subgroup"]["rows"] and result["comparison_with_paper"]
    assert result["missingness"]["Hungary"]["ca"] > 50
    assert "Decision curve analysis" in result["meta"]["extension_analyses"]
    pdf = client.get(f"/api/research/experiments/{made.json()['id']}/report.pdf", headers=r)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/research/experiments/{made.json()['id']}/report.csv", headers=r).text.startswith("model,evaluation")


def test_external_cohorts_never_used_for_fitting(client):
    from app.research.engine import run_validation
    from app.features import CLINICAL, NUMERIC
    frame, _, _ = data_module.load_cohorts(force_synthetic=True)
    types = {f: "numeric" if f in NUMERIC else "categorical" for f in CLINICAL}
    base = run_validation(frame, {"portable_logistic": (CLINICAL, "logistic")}, types, "Cleveland", repeats=1, bootstrap=0, recalibrate=())
    flipped = frame.copy()
    flipped.loc[flipped["site"] != "Cleveland", "target"] = 1 - flipped.loc[flipped["site"] != "Cleveland", "target"]
    again = run_validation(flipped, {"portable_logistic": (CLINICAL, "logistic")}, types, "Cleveland", repeats=1, bootstrap=0, recalibrate=())
    assert base["models"]["portable_logistic"]["internal"]["auc"] == again["models"]["portable_logistic"]["internal"]["auc"]
    h_a = base["models"]["portable_logistic"]["external"]["Hungary"]
    h_b = again["models"]["portable_logistic"]["external"]["Hungary"]
    assert h_a["auc"] != h_b["auc"]


def test_uci_experiment_fails_clearly_when_unavailable(client, clinic, monkeypatch):
    monkeypatch.setattr(data_module, "fetch", lambda site: None)
    r = headers(clinic["researcher"]["access_token"])
    made = client.post("/api/research/experiments", headers=r, json={"name": "UCI replication", "kind": "paper_replication", "source": "uci", **FAST})
    exp = wait_for(client, clinic["researcher"], made.json()["id"])
    assert exp["status"] == "failed" and "processed" in exp["error"]
    assert client.get(f"/api/research/experiments/{made.json()['id']}/report.pdf", headers=r).status_code == 409


def test_provenance_labels():
    from app.research.jobs import provenance_for
    base = {"kind": "paper_replication", "source": "uci", "recode_zeros": False}
    assert provenance_for(base) == "reproduced"
    assert provenance_for({**base, "recode_zeros": True}) == "new_experiment"
    assert provenance_for({**base, "source": "synthetic"}) == "synthetic_demo"
    assert provenance_for({**base, "kind": "custom_validation"}) == "new_experiment"


def test_custom_validation_flow(client, clinic, multi_site_csv):
    r = headers(clinic["researcher"]["access_token"])
    dataset = client.post("/api/research/datasets", headers=r, data={"name": "Custom data"}, files={"file": ("d.csv", upload_csv(multi_site_csv), "text/csv")}).json()
    config = {"name": "Custom validation", "kind": "custom_validation", "dataset_id": dataset["id"], "target_column": "num",
              "site_column": "site", "dev_site": "Cleveland", "feature_columns": ["age", "sex", "cp", "trestbps", "chol", "thalach", "oldpeak", "ca"],
              "group_column": "gender_group", **FAST}
    made = client.post("/api/research/experiments", headers=r, json=config)
    assert made.status_code == 202, made.text
    exp = wait_for(client, clinic["researcher"], made.json()["id"])
    assert exp["status"] == "completed", exp["error"]
    result = exp["result"]
    assert exp["provenance"] == "new_experiment"
    assert "ca" not in result["models"]["portable_logistic"]["features"]
    assert result["availability"]["ca"]["portable"] is False
    assert {row["group"] for row in result["subgroup"]["rows"]} <= {"F", "M"}
    assert "comparison_with_paper" not in result


@pytest.mark.parametrize("change, expected", [
    ({"dev_site": "Nowhere"}, 422), ({"target_column": "missing_col"}, 422), ({"feature_columns": ["num"]}, 422),
    ({"site_column": "age"}, 422)])
def test_custom_config_validation(client, clinic, multi_site_csv, change, expected):
    r = headers(clinic["researcher"]["access_token"])
    dataset = client.post("/api/research/datasets", headers=r, data={"name": "Config checks"}, files={"file": ("d.csv", upload_csv(multi_site_csv), "text/csv")}).json()
    config = {"name": "Bad config", "kind": "custom_validation", "dataset_id": dataset["id"], "target_column": "num", "site_column": "site",
              "dev_site": "Cleveland", "feature_columns": ["age", "sex"], **FAST, **change}
    assert client.post("/api/research/experiments", headers=r, json=config).status_code == expected


def test_researchers_are_isolated(client, clinic):
    r = headers(clinic["researcher"]["access_token"])
    made = client.post("/api/research/experiments", headers=r, json={"name": "Private run", "kind": "paper_replication", "source": "synthetic", **FAST}).json()
    admin = headers(clinic["admin"]["access_token"])
    other = client.post("/api/admin/users", headers=admin, json={"email": "second.researcher@example.org", "password": "Str0ngPassw0rd", "full_name": "Second Researcher", "role": "researcher"})
    if other.status_code == 409:
        pass
    token = client.post("/api/auth/login", json={"email": "second.researcher@example.org", "password": "Str0ngPassw0rd"}).json()["access_token"]
    assert client.get(f"/api/research/experiments/{made['id']}", headers=headers(token)).status_code == 404


def test_models_registry_and_uci_status(client, clinic):
    r = headers(clinic["researcher"]["access_token"])
    models = client.get("/api/research/models", headers=r).json()
    assert models and models[0]["is_active"] and models[0]["data_source"] == "synthetic"
    assert "missing" in client.get("/api/research/uci-status", headers=r).json()
