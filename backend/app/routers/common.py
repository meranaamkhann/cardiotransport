from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.crypto import decrypt
from ..db.models import Assessment, User


def get_engine(request: Request):
    engine = request.app.state.engine
    if engine is None:
        raise HTTPException(503, "The model has not been trained yet. Run: python -m app.training")
    return engine


def user_out(user: User) -> dict:
    profile = user.profile
    complete = bool(profile and profile.sex and profile.birth_year and profile.smoking)
    return {"id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
            "clinic": {"id": user.clinic.id, "name": user.clinic.name,
                       "code": user.clinic.code if user.role in ("clinic_admin", "clinician") else None} if user.clinic else None,
            "profile_complete": complete if user.role == "patient" else None}


def profile_out(user: User) -> dict:
    p = user.profile
    if p is None:
        return {"sex": None, "birth_year": None, "height_cm": None, "smoking": None, "diabetes": False,
                "family_history": False, "conditions": [], "activity_minutes": None}
    return {"sex": p.sex, "birth_year": p.birth_year, "height_cm": p.height_cm, "smoking": p.smoking,
            "diabetes": p.diabetes, "family_history": p.family_history, "conditions": p.conditions or [],
            "activity_minutes": p.activity_minutes}


def assessment_out(a: Assessment, detail: bool = True) -> dict:
    body = {"id": a.id, "patient_id": a.patient_id, "patient_name": a.patient.full_name if a.patient else None,
            "kind": a.kind, "urgency": a.urgency, "status": a.status, "model_version": a.model_version,
            "created_at": a.created_at.isoformat(), "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
            "reviewer": a.reviewer.full_name if a.reviewer else None,
            "headline": a.result.get("final", {}).get("title") if a.kind == "symptom" else a.result.get("headline")}
    if detail:
        body.update({"inputs": a.inputs, "result": a.result,
                     "clinician_summary": decrypt(a.clinician_summary) if a.clinician_summary else None})
    return body


def own_assessment(db: Session, user: User, assessment_id: int) -> Assessment:
    a = db.scalar(select(Assessment).where(Assessment.id == assessment_id, Assessment.patient_id == user.id))
    if a is None:
        raise HTTPException(404, "Assessment not found")
    return a
