import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core import audit
from ..core.crypto import decrypt
from ..core.deps import require
from ..db.base import get_db
from ..core.security import verify_password
from ..db.models import (Appointment, Assessment, AuditEvent, ClinicalNote, Measurement, PatientProfile, Report, User)
from ..schemas import (AppointmentCreate, DeleteAccount, AppointmentUpdate, MeasurementCreate, ProfileUpdate, SymptomAssessment,
                       WellnessAssessment)
from ..services import assessments as svc
from ..services import reports
from ..services.registry import model_tag
from .common import assessment_out, get_engine, own_assessment, profile_out, user_out

router = APIRouter(prefix="/me", tags=["patient"], dependencies=[Depends(require("patient"))])
patient = Depends(require("patient"))

UNITS = {"systolic": "mmHg", "diastolic": "mmHg", "cholesterol": "mg/dL", "glucose": "mg/dL", "weight": "kg", "resting_hr": "bpm"}
RANGES = {"systolic": (70, 260), "diastolic": (40, 160), "cholesterol": (80, 700), "glucose": (40, 700),
          "weight": (30, 250), "resting_hr": (30, 220)}


def appointment_out(a: Appointment) -> dict:
    return {"id": a.id, "scheduled_at": a.scheduled_at.isoformat(), "reason": a.reason, "status": a.status,
            "clinician": a.clinician.full_name if a.clinician else None}


@router.get("/profile")
def get_profile(user: User = patient):
    return profile_out(user)


@router.put("/profile")
def put_profile(payload: ProfileUpdate, request: Request, user: User = patient, db: Session = Depends(get_db)):
    if user.profile is None:
        user.profile = PatientProfile()
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(user.profile, field, value)
    audit.record(db, user, "profile_update", "profile", user.id, request)
    db.commit()
    return {"profile": profile_out(user), "user": user_out(user)}


@router.get("/dashboard")
def dashboard(user: User = patient, db: Session = Depends(get_db)):
    recent = db.scalars(select(Assessment).where(Assessment.patient_id == user.id)
                        .order_by(Assessment.created_at.desc()).limit(5)).all()
    total = db.scalar(select(func.count()).select_from(Assessment).where(Assessment.patient_id == user.id))
    upcoming = db.scalars(select(Appointment).where(Appointment.patient_id == user.id,
                                                    Appointment.status.in_(["requested", "confirmed"]),
                                                    Appointment.scheduled_at >= datetime.now(timezone.utc))
                          .order_by(Appointment.scheduled_at).limit(5)).all()
    return {"user": user_out(user), "profile": profile_out(user), "total_assessments": total,
            "recent": [assessment_out(a, detail=False) for a in recent],
            "latest_measurements": svc.latest_measurements(db, user.id),
            "upcoming": [appointment_out(a) for a in upcoming]}


@router.post("/assessments/symptom", status_code=201)
def symptom(payload: SymptomAssessment, request: Request, user: User = patient, db: Session = Depends(get_db)):
    engine = get_engine(request)
    inputs, result, level, version = svc.run_symptom(db, engine, user, payload)
    row = Assessment(patient_id=user.id, kind="symptom", urgency=level, inputs=inputs, result=result, model_version=version)
    db.add(row)
    db.flush()
    audit.record(db, user, "assessment_created", "assessment", row.id, request, {"kind": "symptom", "urgency": level})
    db.commit()
    return assessment_out(row)


@router.post("/assessments/wellness", status_code=201)
def wellness(payload: WellnessAssessment, request: Request, user: User = patient, db: Session = Depends(get_db)):
    version = model_tag(get_engine(request).card)
    inputs, result, level, version = svc.run_wellness(db, user, payload, version)
    row = Assessment(patient_id=user.id, kind="wellness", urgency=level, inputs=inputs, result=result, model_version=None)
    db.add(row)
    db.flush()
    audit.record(db, user, "assessment_created", "assessment", row.id, request, {"kind": "wellness", "urgency": level})
    db.commit()
    return assessment_out(row)


@router.get("/assessments")
def list_assessments(user: User = patient, db: Session = Depends(get_db), limit: int = 50):
    rows = db.scalars(select(Assessment).where(Assessment.patient_id == user.id)
                      .order_by(Assessment.created_at.desc()).limit(min(limit, 200))).all()
    return [assessment_out(a, detail=False) for a in rows]


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: int, user: User = patient, db: Session = Depends(get_db)):
    return assessment_out(own_assessment(db, user, assessment_id))


@router.get("/assessments/{assessment_id}/report.pdf")
def assessment_report(assessment_id: int, request: Request, user: User = patient, db: Session = Depends(get_db)):
    a = own_assessment(db, user, assessment_id)
    pdf = reports.assessment_pdf(a, user, a.reviewer, decrypt(a.clinician_summary) if a.clinician_summary else None)
    db.add(Report(patient_id=user.id, assessment_id=a.id, created_by=user.id, kind="assessment", sha256=reports.sha(pdf)))
    audit.record(db, user, "report_generated", "assessment", a.id, request)
    db.commit()
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="cardiolens-assessment-{a.id}.pdf"'})


@router.get("/measurements")
def list_measurements(kind: str = None, user: User = patient, db: Session = Depends(get_db), limit: int = 500):
    query = select(Measurement).where(Measurement.patient_id == user.id)
    if kind:
        query = query.where(Measurement.kind == kind)
    rows = db.scalars(query.order_by(Measurement.measured_at.desc()).limit(min(limit, 2000))).all()
    return [{"id": m.id, "kind": m.kind, "value": m.value, "unit": UNITS.get(m.kind), "measured_at": m.measured_at.isoformat()}
            for m in rows]


@router.post("/measurements", status_code=201)
def add_measurement(payload: MeasurementCreate, user: User = patient, db: Session = Depends(get_db)):
    low, high = RANGES[payload.kind]
    if not low <= payload.value <= high:
        raise HTTPException(422, f"{payload.kind} must be between {low} and {high}.")
    when = payload.measured_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    if when > datetime.now(timezone.utc):
        raise HTTPException(422, "Measurement time cannot be in the future.")
    row = Measurement(patient_id=user.id, kind=payload.kind, value=payload.value, measured_at=when)
    db.add(row)
    db.commit()
    return {"id": row.id, "kind": row.kind, "value": row.value, "unit": UNITS[row.kind], "measured_at": row.measured_at.isoformat()}


@router.delete("/measurements/{measurement_id}", status_code=204)
def delete_measurement(measurement_id: int, user: User = patient, db: Session = Depends(get_db)):
    row = db.scalar(select(Measurement).where(Measurement.id == measurement_id, Measurement.patient_id == user.id))
    if row is None:
        raise HTTPException(404, "Measurement not found")
    db.delete(row)
    db.commit()


@router.get("/appointments")
def list_appointments(user: User = patient, db: Session = Depends(get_db)):
    rows = db.scalars(select(Appointment).where(Appointment.patient_id == user.id).order_by(Appointment.scheduled_at.desc())).all()
    return [appointment_out(a) for a in rows]


@router.post("/appointments", status_code=201)
def request_appointment(payload: AppointmentCreate, request: Request, user: User = patient, db: Session = Depends(get_db)):
    if user.clinic_id is None:
        raise HTTPException(422, "Join a clinic with its code before requesting an appointment.")
    when = payload.scheduled_at if payload.scheduled_at.tzinfo else payload.scheduled_at.replace(tzinfo=timezone.utc)
    if when <= datetime.now(timezone.utc):
        raise HTTPException(422, "Choose a time in the future.")
    if payload.clinician_id is not None:
        clinician = db.get(User, payload.clinician_id)
        if clinician is None or clinician.clinic_id != user.clinic_id or clinician.role != "clinician":
            raise HTTPException(422, "That clinician is not part of your clinic.")
    row = Appointment(patient_id=user.id, clinician_id=payload.clinician_id, scheduled_at=when, reason=payload.reason.strip(),
                      created_by=user.id)
    db.add(row)
    db.flush()
    audit.record(db, user, "appointment_requested", "appointment", row.id, request)
    db.commit()
    return appointment_out(row)


@router.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id: int, payload: AppointmentUpdate, user: User = patient, db: Session = Depends(get_db)):
    row = db.scalar(select(Appointment).where(Appointment.id == appointment_id, Appointment.patient_id == user.id))
    if row is None:
        raise HTTPException(404, "Appointment not found")
    if payload.status != "cancelled":
        raise HTTPException(403, "Patients can only cancel appointments.")
    row.status = "cancelled"
    db.commit()
    return appointment_out(row)


@router.get("/clinicians")
def clinic_clinicians(user: User = patient, db: Session = Depends(get_db)):
    if user.clinic_id is None:
        return []
    rows = db.scalars(select(User).where(User.clinic_id == user.clinic_id, User.role == "clinician", User.is_active.is_(True))).all()
    return [{"id": c.id, "name": c.full_name} for c in rows]


@router.get("/export/measurements.csv")
def export_measurements(user: User = patient, db: Session = Depends(get_db)):
    rows = db.scalars(select(Measurement).where(Measurement.patient_id == user.id).order_by(Measurement.measured_at)).all()
    body = reports.to_csv(["measured_at", "kind", "value", "unit"], [[m.measured_at.isoformat(), m.kind, m.value, UNITS.get(m.kind)] for m in rows])
    return Response(body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="measurements.csv"'})


@router.get("/export/assessments.csv")
def export_assessments(user: User = patient, db: Session = Depends(get_db)):
    rows = db.scalars(select(Assessment).where(Assessment.patient_id == user.id).order_by(Assessment.created_at)).all()
    body = reports.to_csv(["created_at", "kind", "urgency", "status", "headline"],
                          [[a.created_at.isoformat(), a.kind, a.urgency, a.status, assessment_out(a, False)["headline"]] for a in rows])
    return Response(body, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="assessments.csv"'})


@router.get("/access-log")
def access_log(user: User = patient, db: Session = Depends(get_db), limit: int = 100):
    rows = db.scalars(select(AuditEvent).where(AuditEvent.entity == "patient", AuditEvent.entity_id == user.id,
                                               AuditEvent.actor_id != user.id)
                      .order_by(AuditEvent.created_at.desc()).limit(min(limit, 300))).all()
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_([r.actor_id for r in rows if r.actor_id])))}
    return [{"id": e.id, "who": names.get(e.actor_id, "A former clinic member"), "action": e.action.replace("_", " "),
             "when": e.created_at.isoformat()} for e in rows]


@router.get("/export.json")
def export_everything(request: Request, user: User = patient, db: Session = Depends(get_db)):
    assessments = db.scalars(select(Assessment).where(Assessment.patient_id == user.id).order_by(Assessment.created_at)).all()
    measurements = db.scalars(select(Measurement).where(Measurement.patient_id == user.id).order_by(Measurement.measured_at)).all()
    appointments = db.scalars(select(Appointment).where(Appointment.patient_id == user.id).order_by(Appointment.scheduled_at)).all()
    audit.record(db, user, "account_exported", "user", user.id, request)
    db.commit()
    body = {"exported_at": datetime.now(timezone.utc).isoformat(), "account": user_out(user), "profile": profile_out(user),
            "assessments": [assessment_out(a) for a in assessments],
            "measurements": [{"kind": m.kind, "value": m.value, "unit": UNITS.get(m.kind), "measured_at": m.measured_at.isoformat()} for m in measurements],
            "appointments": [appointment_out(a) for a in appointments]}
    return Response(json.dumps(body, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="cardiolens-my-data.json"'})


@router.post("/delete-account", status_code=204)
def delete_account(payload: DeleteAccount, request: Request, user: User = patient, db: Session = Depends(get_db)):
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(403, "That password is not correct.")
    clinic_id = user.clinic_id
    db.query(ClinicalNote).filter(ClinicalNote.patient_id == user.id).delete()
    db.query(Report).filter(Report.patient_id == user.id).delete()
    db.query(Appointment).filter(Appointment.patient_id == user.id).delete()
    db.query(Measurement).filter(Measurement.patient_id == user.id).delete()
    db.query(Assessment).filter(Assessment.patient_id == user.id).delete()
    db.query(AuditEvent).filter(AuditEvent.actor_id == user.id).update({"actor_id": None})
    db.query(PatientProfile).filter(PatientProfile.user_id == user.id).delete()
    db.delete(user)
    audit.record(db, None, "account_deleted", "user", None, request, clinic_id=clinic_id)
    db.commit()
