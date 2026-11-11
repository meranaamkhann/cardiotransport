import numpy as np
import pandas as pd

from app import data
from app.schemas import Wellness
from app.training import wilson
from app.wellness import assess_wellness, bp_status

BASE = dict(pathway="symptomatic", age=58, sex="male", chest_pain="atypical", exercise_pain=False,
            systolic=135, cholesterol=220, fasting_glucose=95)


def test_model_card_and_bands(client):
    card = client.get("/api/model-card").json()
    assert set(card["deployment"]) == {"core", "clinical"}
    for tier in card["deployment"].values():
        assert tier["bands"]["lower_cut"] < tier["bands"]["higher_cut"]
        assert set(tier["held_out_site"]) == {"Cleveland", "Hungary", "Switzerland", "Long Beach VA"}


def test_public_assess_and_tiers(client):
    base = client.post("/api/public/assess", json=BASE).json()
    full = client.post("/api/public/assess", json={**BASE, "ecg": "normal", "max_hr": 150, "st_depression": 0.5}).json()
    partial = client.post("/api/public/assess", json={**BASE, "ecg": "normal", "max_hr": 150}).json()
    assert base["tier"] == "core" and partial["tier"] == "core" and full["tier"] == "clinical"
    assert base["observed"]["n"] > 0 and 0 <= base["model_score"] <= 100


def test_public_validation(client):
    assert client.post("/api/public/assess", json={**BASE, "chest_pain": "none"}).status_code == 422
    assert client.post("/api/public/assess", json={**BASE, "pathway": "referred", "chest_pain": "none"}).status_code == 200


def test_safety_rules(client):
    emergency = client.post("/api/public/assess", json={**BASE, "emergency": ["pain_at_rest"]}).json()
    assert emergency["band"] == "higher" and emergency["emergency"]["active"]
    young = {**BASE, "age": 30, "sex": "female", "chest_pain": "typical", "exercise_pain": True, "systolic": 105, "cholesterol": 150, "fasting_glucose": 80}
    assert client.post("/api/public/assess", json=young).json()["band"] != "lower"


def test_missing_values_reduce_confidence(client):
    order = {"good": 0, "fair": 1, "limited": 2}
    full = client.post("/api/public/assess", json=BASE).json()
    sparse = client.post("/api/public/assess", json={**BASE, "systolic": None, "cholesterol": None, "fasting_glucose": None}).json()
    assert order[sparse["confidence"]["level"]] > order[full["confidence"]["level"]]


def test_out_of_range_warning(client):
    assert any("outside" in w for w in client.post("/api/public/assess", json={**BASE, "age": 95}).json()["warnings"])


def test_wellness_rules():
    ok = assess_wellness(Wellness(age=45, sex="female", systolic=118, diastolic=76, cholesterol=180, fasting_glucose=90,
                                  height_cm=162, weight_kg=55, smoking="never", activity_minutes=200))
    assert ok["overall"] == "good"
    crisis = assess_wellness(Wellness(age=60, sex="male", systolic=190, diastolic=125, smoking="current"))
    assert crisis["overall"] == "urgent"
    assert bp_status(119, 79) == "normal" and bp_status(135, 70) == "stage1" and bp_status(None, None) is None


def test_zero_values_are_recoded_unless_replicating():
    raw = pd.DataFrame({"chol": [0, 200, 0], "trestbps": [0, 120, 130], "num": [0, 1, 2]})
    assert data.clean(raw)["chol"].isna().sum() == 2
    assert data.clean(raw, recode_zeros=False)["chol"].isna().sum() == 0
    assert list(data.clean(raw)["target"]) == [0, 1, 1]


def test_wilson_interval():
    low, high = wilson(5, 20)
    assert 0 < low < 0.25 < high < 1
