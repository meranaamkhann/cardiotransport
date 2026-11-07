import io

import numpy as np
import pandas as pd

from app import clinic, data
from app.schemas import Wellness
from app.training import wilson
from app.wellness import assess_wellness, bp_status

BASE = dict(pathway="symptomatic", age=58, sex="male", chest_pain="atypical", exercise_pain=False,
            systolic=135, cholesterol=220, fasting_glucose=95)


def test_health_and_card(client):
    assert client.get("/api/health").json()["status"] == "ok"
    card = client.get("/api/model-card").json()
    assert set(card["deployment"]) == {"core", "clinical"}
    assert card["deployment"]["core"]["bands"]["lower_cut"] < card["deployment"]["core"]["bands"]["higher_cut"]


def test_assess_basic(client):
    r = client.post("/api/assess", json=BASE)
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "core"
    assert body["band"] in {"lower", "moderate", "higher"}
    assert 0 <= body["model_score"] <= 100
    assert body["observed"]["n"] > 0


def test_clinical_tier_needs_all_three_reports(client):
    partial = client.post("/api/assess", json={**BASE, "ecg": "normal", "max_hr": 150}).json()
    full = client.post("/api/assess", json={**BASE, "ecg": "normal", "max_hr": 150, "st_depression": 0.5}).json()
    assert partial["tier"] == "core"
    assert full["tier"] == "clinical"


def test_symptomatic_cannot_pick_no_pain(client):
    assert client.post("/api/assess", json={**BASE, "chest_pain": "none"}).status_code == 422


def test_referred_can_pick_no_pain(client):
    assert client.post("/api/assess", json={**BASE, "pathway": "referred", "chest_pain": "none"}).status_code == 200


def test_emergency_overrides_band(client):
    body = client.post("/api/assess", json={**BASE, "emergency": ["pain_at_rest"]}).json()
    assert body["emergency"]["active"] is True
    assert body["band"] == "higher"


def test_exertional_pain_never_scores_lower(client):
    young = {**BASE, "age": 30, "sex": "female", "chest_pain": "typical", "exercise_pain": True,
             "systolic": 105, "cholesterol": 150, "fasting_glucose": 80}
    assert client.post("/api/assess", json=young).json()["band"] != "lower"


def test_unknown_values_lower_confidence(client):
    full = client.post("/api/assess", json=BASE).json()
    sparse = client.post("/api/assess", json={**BASE, "systolic": None, "cholesterol": None,
                                              "fasting_glucose": None}).json()
    order = {"good": 0, "fair": 1, "limited": 2}
    assert order[sparse["confidence"]["level"]] > order[full["confidence"]["level"]]


def test_out_of_range_warns(client):
    body = client.post("/api/assess", json={**BASE, "age": 95}).json()
    assert any("outside" in w for w in body["warnings"])


def test_local_calibration_changes_probability(client):
    cal = {"tier": "core", "intercept": 1.0, "slope": 1.0, "label": "Test clinic", "n": 80}
    body = client.post("/api/assess", json={**BASE, "local_calibrations": [cal]}).json()
    assert body["local"]["label"] == "Test clinic"
    assert 0 < body["local"]["probability"] < 1


def test_clinic_calibration_flow(client):
    frame, _, _ = data.load_cohorts(force_synthetic=True)
    local = frame[frame["site"] == "Switzerland"].copy()
    local["outcome"] = local["target"]
    csv = local[clinic.CLINICAL + ["outcome"]].to_csv(index=False)
    r = client.post("/api/clinic/calibrate", files={"file": ("local.csv", csv, "text/csv")}, data={"site_name": "Zurich"})
    assert r.status_code == 200
    body = r.json()
    core = next(x for x in body["results"] if x["tier"] == "core")
    assert core["brier_after"] <= core["brier_before"]
    assert body["site_name"] == "Zurich"


def test_clinic_rejects_small_files(client):
    csv = "age,sex,cp,exang,trestbps,chol,fbs,outcome\n50,1,4,1,130,200,0,1\n"
    r = client.post("/api/clinic/calibrate", files={"file": ("x.csv", csv, "text/csv")})
    assert r.status_code == 422


def test_clinic_rejects_missing_columns(client):
    r = client.post("/api/clinic/calibrate", files={"file": ("x.csv", "age,sex\n1,2\n", "text/csv")})
    assert r.status_code == 422


def test_template_download(client):
    r = client.get("/api/clinic/template")
    assert r.status_code == 200
    assert r.text.splitlines()[0].startswith("age,sex,cp")


def test_wellness_endpoint(client):
    payload = dict(age=45, sex="female", systolic=118, diastolic=76, cholesterol=180, fasting_glucose=90,
                   height_cm=162, weight_kg=55, smoking="never", activity_minutes=200)
    body = client.post("/api/wellness", json=payload).json()
    assert body["overall"] == "good"


def test_wellness_flags_crisis():
    w = Wellness(age=60, sex="male", systolic=190, diastolic=125, smoking="current")
    result = assess_wellness(w)
    assert result["overall"] == "urgent"
    assert bp_status(119, 79) == "normal"
    assert bp_status(135, 70) == "stage1"
    assert bp_status(None, None) is None


def test_zero_cholesterol_is_recoded():
    raw = pd.DataFrame({"chol": [0, 200, 0], "trestbps": [0, 120, 130], "num": [0, 1, 2]})
    cleaned = data.clean(raw)
    assert cleaned["chol"].isna().sum() == 2
    assert cleaned["trestbps"].isna().sum() == 1
    assert list(cleaned["target"]) == [0, 1, 1]


def test_wilson_interval_bounds():
    low, high = wilson(5, 20)
    assert 0 < low < 0.25 < high < 1
