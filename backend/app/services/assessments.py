from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import ClinicCalibration, Measurement, PatientProfile, User
from ..engine import Engine
from ..schemas import Assessment, LocalCalibration, SymptomAssessment, Wellness, WellnessAssessment
from ..wellness import assess_wellness
from .registry import model_tag
from .triage import LEVEL_TEXT, higher, triage

BAND_LEVEL = {"lower": "routine", "moderate": "soon", "higher": "prompt"}
WELLNESS_LEVEL = {"urgent": "urgent", "several": "soon", "some": "routine", "good": "routine"}


def latest_measurements(db: Session, patient_id: int) -> dict:
    latest = {}
    rows = db.scalars(select(Measurement).where(Measurement.patient_id == patient_id)
                      .order_by(Measurement.measured_at.desc())).all()
    for row in rows:
        latest.setdefault(row.kind, row.value)
    return latest


def clinic_calibrations(db: Session, clinic_id: Optional[int]) -> list:
    if clinic_id is None:
        return []
    rows = db.scalars(select(ClinicCalibration).where(ClinicCalibration.clinic_id == clinic_id,
                                                      ClinicCalibration.is_active.is_(True))
                      .order_by(ClinicCalibration.created_at.desc())).all()
    seen, out = set(), []
    for row in rows:
        if row.tier not in seen:
            seen.add(row.tier)
            out.append(LocalCalibration(tier=row.tier, intercept=row.intercept, slope=row.slope,
                                        label="your clinic", n=row.n))
    return out


def age_and_sex(profile: Optional[PatientProfile]):
    if profile is None or not profile.sex or not profile.birth_year:
        raise HTTPException(422, "Please complete your profile (sex and birth year) before taking an assessment.")
    age = datetime.now(timezone.utc).year - profile.birth_year
    if age < 18 or age > 100:
        raise HTTPException(422, "Assessments are available for adults aged 18 to 100.")
    return age, profile.sex


def run_symptom(db: Session, engine: Engine, user: User, payload: SymptomAssessment):
    age, sex = age_and_sex(user.profile)
    latest = latest_measurements(db, user.id)
    filled = []

    def pick(value, key, name):
        if value is not None:
            return value
        if key in latest:
            filled.append(name)
            return latest[key]
        return None

    systolic = pick(payload.systolic, "systolic", "systolic")
    cholesterol = pick(payload.cholesterol, "cholesterol", "cholesterol")
    glucose = pick(payload.fasting_glucose, "glucose", "fasting_glucose")
    tri = triage(payload)
    model, model_note = None, None
    if payload.chest_discomfort != "none":
        engine_input = Assessment(
            pathway="symptomatic", age=age, sex=sex, chest_pain=payload.chest_discomfort,
            exercise_pain=payload.discomfort_with_effort, systolic=systolic, cholesterol=cholesterol,
            fasting_glucose=glucose, ecg=payload.ecg, max_hr=payload.max_hr, st_depression=payload.st_depression,
            emergency=payload.emergency, local_calibrations=clinic_calibrations(db, user.clinic_id))
        model = engine.assess(engine_input)
    else:
        model_note = ("The research model was built from patients who had chest pain or were referred for a heart "
                      "evaluation, so it was not used for your answers.")
    final = tri["level"]
    if model:
        final = higher(final, BAND_LEVEL[model["band"]])
    title, message = LEVEL_TEXT[final]
    inputs = {**payload.model_dump(), "age": age, "sex": sex, "autofilled_from_history": filled}
    result = {
        "provenance": {"symptoms": "patient-reported", "triage": "rule-based, not a diagnosis",
                       "model": "research model trained on historical angiography records"},
        "triage": tri, "model": model, "model_note": model_note,
        "final": {"level": final, "title": title, "message": message,
                  "rule": "The final level is the highest of the triage rules and the model band. A low model score never lowers it."},
    }
    return inputs, result, final, model_tag(engine.card)


def run_wellness(db: Session, user: User, payload: WellnessAssessment, version: str):
    age, sex = age_and_sex(user.profile)
    profile = user.profile
    if not profile.smoking:
        raise HTTPException(422, "Please add your smoking status to your profile first.")
    latest = latest_measurements(db, user.id)
    filled = []

    def pick(value, key, name):
        if value is not None:
            return value
        if key in latest:
            filled.append(name)
            return latest[key]
        return None

    systolic = pick(payload.systolic, "systolic", "systolic")
    diastolic = pick(payload.diastolic, "diastolic", "diastolic")
    cholesterol = pick(payload.cholesterol, "cholesterol", "cholesterol")
    glucose = pick(payload.fasting_glucose, "glucose", "fasting_glucose")
    weight = pick(payload.weight_kg, "weight", "weight_kg")
    activity = payload.activity_minutes if payload.activity_minutes is not None else profile.activity_minutes
    model = Wellness(age=age, sex=sex, systolic=systolic, diastolic=diastolic, cholesterol=cholesterol,
                     fasting_glucose=glucose, height_cm=profile.height_cm, weight_kg=weight,
                     smoking=profile.smoking, diabetes=profile.diabetes or "diabetes" in profile.conditions,
                     family_history=profile.family_history or "family_history" in profile.conditions,
                     activity_minutes=activity, south_asian_cutoffs=payload.south_asian_cutoffs)
    outcome = assess_wellness(model)
    level = WELLNESS_LEVEL[outcome["overall"]]
    outcome["provenance"] = {"values": "patient-reported", "assessment": "guideline thresholds, not a prediction or diagnosis"}
    inputs = {**payload.model_dump(), "age": age, "sex": sex, "autofilled_from_history": filled}
    if payload.save_measurements:
        now = datetime.now(timezone.utc)
        for kind, value in (("systolic", payload.systolic), ("diastolic", payload.diastolic),
                            ("cholesterol", payload.cholesterol), ("glucose", payload.fasting_glucose),
                            ("weight", payload.weight_kg)):
            if value is not None:
                db.add(Measurement(patient_id=user.id, kind=kind, value=value, measured_at=now))
    return inputs, outcome, level, version
