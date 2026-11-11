from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import recalibration
from ..core import audit
from ..core.crypto import decrypt, encrypt
from ..core.deps import require
from ..db.base import get_db
from ..db.models import Appointment, Assessment, ClinicalNote, ClinicCalibration, Measurement, Report, User
from ..schemas import AppointmentCreate, AppointmentUpdate, NoteCreate, ReviewCreate
from ..services import reports
from ..services.triage import rank
from .common import assessment_out, get_engine, profile_out
from .patient import UNITS, appointment_out

router = APIRouter(prefix="/clinic", tags=["clinic"])
clinician = Depends(require("clinician"))
staff = Depends(require("clinician", "clinic_admin"))


def clinic_patient(db: Session, user: User, patient_id: int) -> User:
    patient = db.scalar(select(User).where(User.id == patient_id, User.role == "patient", User.clinic_id == user.clinic_id))
    if patient is None:
        raise HTTPException(404, "Patient not found")
    return patient


def clinic_assessment(db: Session, user: User, assessment_id: int) -> Assessment:
    row = db.get(Assessment, assessment_id)
    if row is None or row.patient.clinic_id != user.clinic_id or row.patient.clinic_id is None:
        raise HTTPException(404, "Assessment not found")
    return row


@router.get("/patients")
def patients(q: str = "", user: User = clinician, db: Session = Depends(get_db)):
    query = select(User).where(User.role == "patient", User.clinic_id == user.clinic_id, User.is_active.is_(True))
    if q.strip():
        query = query.where(func.lower(User.full_name).contains(q.strip().lower()))
    rows = db.scalars(query.order_by(User.full_name).limit(200)).all()
    out = []
    for p in rows:
        last = db.scalar(select(Assessment).where(Assessment.patient_id == p.id).order_by(Assessment.created_at.desc()))
        pending = db.scalar(select(func.count()).select_from(Assessment).where(Assessment.patient_id == p.id, Assessment.status == "submitted"))
        out.append({"id": p.id, "name": p.full_name, "email": p.email,
                    "last_assessment": assessment_out(last, detail=False) if last else None, "pending_review": pending})
    return out


@router.get("/queue")
def queue(user: User = clinician, db: Session = Depends(get_db)):
    rows = db.scalars(select(Assessment).join(User, Assessment.patient_id == User.id)
                      .where(User.clinic_id == user.clinic_id, Assessment.status == "submitted")
                      .order_by(Assessment.created_at.desc()).limit(200)).all()
    rows.sort(key=lambda a: (-rank(a.urgency), a.created_at))
    return [assessment_out(a, detail=False) for a in rows]


@router.get("/patients/{patient_id}")
def patient_detail(patient_id: int, request: Request, user: User = clinician, db: Session = Depends(get_db)):
    p = clinic_patient(db, user, patient_id)
    audit.record(db, user, "patient_record_viewed", "patient", p.id, request)
    db.commit()
    assessments = db.scalars(select(Assessment).where(Assessment.patient_id == p.id).order_by(Assessment.created_at.desc()).limit(100)).all()
    measurements = db.scalars(select(Measurement).where(Measurement.patient_id == p.id).order_by(Measurement.measured_at.desc()).limit(300)).all()
    notes = db.scalars(select(ClinicalNote).where(ClinicalNote.patient_id == p.id).order_by(ClinicalNote.created_at.desc())).all()
    appointments = db.scalars(select(Appointment).where(Appointment.patient_id == p.id).order_by(Appointment.scheduled_at.desc())).all()
    return {"patient": {"id": p.id, "name": p.full_name, "email": p.email}, "profile": profile_out(p),
            "assessments": [assessment_out(a) for a in assessments],
            "measurements": [{"id": m.id, "kind": m.kind, "value": m.value, "unit": UNITS.get(m.kind), "measured_at": m.measured_at.isoformat()} for m in measurements],
            "notes": [{"id": n.id, "author": n.author.full_name, "assessment_id": n.assessment_id, "body": decrypt(n.body_encrypted), "created_at": n.created_at.isoformat()} for n in notes],
            "appointments": [{**appointment_out(a)} for a in appointments]}


@router.post("/assessments/{assessment_id}/review")
def review(assessment_id: int, payload: ReviewCreate, request: Request, user: User = clinician, db: Session = Depends(get_db)):
    a = clinic_assessment(db, user, assessment_id)
    a.status, a.reviewed_by, a.reviewed_at = "reviewed", user.id, datetime.now(timezone.utc)
    a.clinician_summary = encrypt(payload.summary.strip())
    audit.record(db, user, "assessment_reviewed", "assessment", a.id, request)
    db.commit()
    db.refresh(a)
    return assessment_out(a)


@router.post("/patients/{patient_id}/notes", status_code=201)
def add_note(patient_id: int, payload: NoteCreate, request: Request, user: User = clinician, db: Session = Depends(get_db)):
    p = clinic_patient(db, user, patient_id)
    if payload.assessment_id is not None:
        a = db.get(Assessment, payload.assessment_id)
        if a is None or a.patient_id != p.id:
            raise HTTPException(422, "That assessment does not belong to this patient.")
    note = ClinicalNote(patient_id=p.id, author_id=user.id, assessment_id=payload.assessment_id, body_encrypted=encrypt(payload.body.strip()))
    db.add(note)
    db.flush()
    audit.record(db, user, "note_added", "note", note.id, request)
    db.commit()
    return {"id": note.id, "author": user.full_name, "assessment_id": note.assessment_id, "body": payload.body.strip(), "created_at": note.created_at.isoformat()}


@router.post("/patients/{patient_id}/appointments", status_code=201)
def schedule(patient_id: int, payload: AppointmentCreate, request: Request, user: User = clinician, db: Session = Depends(get_db)):
    p = clinic_patient(db, user, patient_id)
    when = payload.scheduled_at if payload.scheduled_at.tzinfo else payload.scheduled_at.replace(tzinfo=timezone.utc)
    row = Appointment(patient_id=p.id, clinician_id=user.id, scheduled_at=when, reason=payload.reason.strip(), status="confirmed", created_by=user.id)
    db.add(row)
    db.flush()
    audit.record(db, user, "appointment_scheduled", "appointment", row.id, request)
    db.commit()
    return appointment_out(row)


@router.patch("/appointments/{appointment_id}")
def update_appointment(appointment_id: int, payload: AppointmentUpdate, user: User = clinician, db: Session = Depends(get_db)):
    row = db.get(Appointment, appointment_id)
    if row is None or db.get(User, row.patient_id).clinic_id != user.clinic_id:
        raise HTTPException(404, "Appointment not found")
    row.status = payload.status
    if payload.scheduled_at:
        row.scheduled_at = payload.scheduled_at if payload.scheduled_at.tzinfo else payload.scheduled_at.replace(tzinfo=timezone.utc)
    row.clinician_id = row.clinician_id or user.id
    db.commit()
    return appointment_out(row)


@router.get("/assessments/{assessment_id}/report.pdf")
def report(assessment_id: int, request: Request, user: User = clinician, db: Session = Depends(get_db)):
    a = clinic_assessment(db, user, assessment_id)
    pdf = reports.assessment_pdf(a, a.patient, a.reviewer, decrypt(a.clinician_summary) if a.clinician_summary else None)
    db.add(Report(patient_id=a.patient_id, assessment_id=a.id, created_by=user.id, kind="assessment", sha256=reports.sha(pdf)))
    audit.record(db, user, "report_generated", "assessment", a.id, request)
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="cardiolens-assessment-{a.id}.pdf"'})


@router.get("/patients/{patient_id}/export/assessments.csv")
def export_assessments(patient_id: int, request: Request, user: User = clinician, db: Session = Depends(get_db)):
    p = clinic_patient(db, user, patient_id)
    rows = db.scalars(select(Assessment).where(Assessment.patient_id == p.id).order_by(Assessment.created_at)).all()
    audit.record(db, user, "export_assessments", "patient", p.id, request)
    db.commit()
    body = reports.to_csv(["created_at", "kind", "urgency", "status", "headline"],
                          [[a.created_at.isoformat(), a.kind, a.urgency, a.status, assessment_out(a, False)["headline"]] for a in rows])
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="patient-{p.id}-assessments.csv"'})


@router.get("/patients/{patient_id}/export/measurements.csv")
def export_measurements(patient_id: int, request: Request, user: User = clinician, db: Session = Depends(get_db)):
    p = clinic_patient(db, user, patient_id)
    rows = db.scalars(select(Measurement).where(Measurement.patient_id == p.id).order_by(Measurement.measured_at)).all()
    audit.record(db, user, "export_measurements", "patient", p.id, request)
    db.commit()
    body = reports.to_csv(["measured_at", "kind", "value", "unit"], [[m.measured_at.isoformat(), m.kind, m.value, UNITS.get(m.kind)] for m in rows])
    return Response(body, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="patient-{p.id}-measurements.csv"'})


def calibration_out(c: ClinicCalibration) -> dict:
    return {"id": c.id, "tier": c.tier, "method": c.method, "intercept": c.intercept, "slope": c.slope, "n": c.n, "events": c.events,
            "brier_before": c.brier_before, "brier_after": c.brier_after, "is_active": c.is_active, "created_at": c.created_at.isoformat()}


@router.get("/calibration")
def list_calibrations(user: User = staff, db: Session = Depends(get_db)):
    rows = db.scalars(select(ClinicCalibration).where(ClinicCalibration.clinic_id == user.clinic_id).order_by(ClinicCalibration.created_at.desc()).limit(20)).all()
    return [calibration_out(c) for c in rows]


@router.get("/calibration/template", response_class=Response)
def calibration_template():
    return Response(recalibration.template_csv(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="cardiolens_template.csv"'})


@router.post("/calibration")
async def calibrate(request: Request, file: UploadFile = File(...), apply: bool = Form(default=False),
                    user: User = staff, db: Session = Depends(get_db)):
    raw = await file.read()
    try:
        result = recalibration.calibrate_upload(get_engine(request), raw)
    except ValueError as error:
        raise HTTPException(422, str(error))
    if apply:
        for tier in result["results"]:
            for old in db.scalars(select(ClinicCalibration).where(ClinicCalibration.clinic_id == user.clinic_id, ClinicCalibration.tier == tier["tier"], ClinicCalibration.is_active.is_(True))):
                old.is_active = False
            db.add(ClinicCalibration(clinic_id=user.clinic_id, tier=tier["tier"], intercept=tier["intercept"], slope=tier["slope"], method=tier["method"],
                                     n=tier["n"], events=tier["events"], brier_before=tier["brier_before"], brier_after=tier["brier_after"], created_by=user.id))
        audit.record(db, user, "calibration_applied", "clinic", user.clinic_id, request)
        db.commit()
    result["applied"] = apply
    return result


@router.delete("/calibration/{calibration_id}", status_code=204)
def deactivate_calibration(calibration_id: int, request: Request, user: User = staff, db: Session = Depends(get_db)):
    row = db.get(ClinicCalibration, calibration_id)
    if row is None or row.clinic_id != user.clinic_id:
        raise HTTPException(404, "Calibration not found")
    row.is_active = False
    audit.record(db, user, "calibration_deactivated", "clinic", user.clinic_id, request)
    db.commit()
