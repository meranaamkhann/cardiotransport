import io
import math
import time
from collections import defaultdict, deque
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from . import research_demo, research_engine
from .models import Assessment, Audit, Experiment, Note, User
from .schemas import Assessment as SymptomInput
from .schemas import Wellness
from .security import hash_password, make_token, read_token, verify_password
from .wellness import assess_wellness

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MAX_UPLOAD = 10 * 1024 * 1024
PROVENANCE = {"inputs": "patient_reported", "assessment": "model_generated", "notes": "clinician_reviewed"}


class Register(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=10, max_length=128)
    clinic: Optional[str] = Field(default=None, max_length=60)


class StaffCreate(Register):
    role: Literal["clinician", "researcher", "admin"]


class Login(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=128)


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class Limiter:
    def __init__(self, limit, window):
        self.limit, self.window, self.hits = limit, window, defaultdict(deque)

    def hit(self, key):
        now, queue = time.time(), self.hits[key]
        while queue and now - queue[0] > self.window:
            queue.popleft()
        if len(queue) >= self.limit:
            raise HTTPException(429, "Too many attempts. Try again in a minute.")
        queue.append(now)


def clean(value):
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def build_router(ctx):
    router = APIRouter(prefix="/api")
    bearer = HTTPBearer(auto_error=False)

    def db():
        session = ctx.Session()
        try:
            yield session
        finally:
            session.close()

    def current(cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer), s: Session = Depends(db)):
        if cred is None:
            raise HTTPException(401, "Authentication required.")
        try:
            claims = read_token(ctx.secret, cred.credentials)
            user = s.get(User, int(claims["sub"]))
        except Exception:
            raise HTTPException(401, "Invalid or expired token.")
        if user is None or not user.active:
            raise HTTPException(401, "Invalid or expired token.")
        return user

    def need(*roles):
        def dependency(user: User = Depends(current)):
            if user.role not in roles:
                raise HTTPException(403, "Your role cannot do this.")
            return user
        return dependency

    def audit(s, user, action, target=""):
        s.add(Audit(user_id=user.id if user else None, action=action, target=str(target)[:120]))
        s.commit()

    def token_for(user):
        return {"access_token": make_token(ctx.secret, user.id, user.role, ctx.token_minutes),
                "token_type": "bearer", "role": user.role, "name": user.name}

    def summary(a):
        return {"id": a.id, "kind": a.kind, "band": a.band, "emergency": a.emergency, "status": a.status,
                "created_at": a.created_at.isoformat(), "model_version": a.model_version}

    def detail(a):
        return {**summary(a), "payload": a.payload, "result": a.result, "provenance": PROVENANCE,
                "notes": [{"id": n.id, "author": n.author.name, "body": n.body, "created_at": n.created_at.isoformat(),
                           "source": "clinician_reviewed"} for n in a.notes]}

    def own(s, user, aid):
        a = s.get(Assessment, aid)
        if a is None or a.patient_id != user.id:
            raise HTTPException(404, "Assessment not found.")
        return a

    def in_scope(s, staff, aid):
        a = s.get(Assessment, aid)
        patient = s.get(User, a.patient_id) if a else None
        if a is None or not staff.clinic or patient.clinic != staff.clinic:
            raise HTTPException(404, "Assessment not found.")
        return a

    @router.post("/auth/register", status_code=201)
    def register(body: Register, s: Session = Depends(db)):
        email = body.email.lower()
        if s.query(User).filter_by(email=email).first():
            raise HTTPException(409, "That email is already registered.")
        user = User(email=email, name=body.name.strip(), role="patient", password_hash=hash_password(body.password),
                    clinic=(body.clinic or "").strip().lower() or None)
        s.add(user)
        s.commit()
        audit(s, user, "register")
        return token_for(user)

    @router.post("/auth/login")
    def login(body: Login, request: Request, s: Session = Depends(db)):
        email = body.email.lower()
        ctx.limiter.hit(f"{request.client.host if request.client else '-'}:{email}")
        user = s.query(User).filter_by(email=email).first()
        stored = user.password_hash if user else hash_password("not-a-real-password")
        if not verify_password(body.password, stored) or user is None or not user.active:
            audit(s, None, "login_failed", email)
            raise HTTPException(401, "Email or password is incorrect.")
        audit(s, user, "login")
        return token_for(user)

    @router.get("/auth/me")
    def me(user: User = Depends(current)):
        return {"id": user.id, "email": user.email, "name": user.name, "role": user.role, "clinic": user.clinic}

    @router.post("/admin/users", status_code=201)
    def create_staff(body: StaffCreate, admin: User = Depends(need("admin")), s: Session = Depends(db)):
        email = body.email.lower()
        if s.query(User).filter_by(email=email).first():
            raise HTTPException(409, "That email is already registered.")
        clinic = (body.clinic or admin.clinic or "").strip().lower() or None
        if body.role in ("clinician", "admin") and not clinic:
            raise HTTPException(422, "Clinicians and clinic administrators need a clinic.")
        user = User(email=email, name=body.name.strip(), role=body.role, clinic=clinic,
                    password_hash=hash_password(body.password))
        s.add(user)
        s.commit()
        audit(s, admin, "create_staff", f"{body.role}:{user.id}")
        return {"id": user.id, "role": user.role, "clinic": user.clinic}

    def store(s, user, kind, payload, result):
        row = Assessment(patient_id=user.id, kind=kind, payload=clean(payload.model_dump()), result=clean(result),
                         model_version=str(result.get("model_version", "rules-1")), band=result.get("band"),
                         emergency=bool(result.get("emergency", {}).get("active")))
        s.add(row)
        s.commit()
        audit(s, user, f"assessment_{kind}", row.id)
        return {**summary(row), "result": row.result, "provenance": PROVENANCE}

    @router.post("/patient/assessments/symptom", status_code=201)
    def submit_symptom(body: SymptomInput, user: User = Depends(need("patient")), s: Session = Depends(db)):
        return store(s, user, "symptom", body, ctx.engine().assess(body))

    @router.post("/patient/assessments/wellness", status_code=201)
    def submit_wellness(body: Wellness, user: User = Depends(need("patient")), s: Session = Depends(db)):
        return store(s, user, "wellness", body, assess_wellness(body))

    @router.get("/patient/assessments")
    def history(user: User = Depends(need("patient")), s: Session = Depends(db)):
        rows = s.query(Assessment).filter_by(patient_id=user.id).order_by(Assessment.id.desc()).all()
        return [summary(a) for a in rows]

    @router.get("/patient/assessments/{aid}")
    def one(aid: int, user: User = Depends(need("patient")), s: Session = Depends(db)):
        return detail(own(s, user, aid))

    @router.get("/patient/export.csv", response_class=PlainTextResponse)
    def export(user: User = Depends(need("patient")), s: Session = Depends(db)):
        rows = s.query(Assessment).filter_by(patient_id=user.id).order_by(Assessment.id).all()
        frame = pd.DataFrame([summary(a) for a in rows], columns=["id", "kind", "band", "emergency", "status",
                                                                  "created_at", "model_version"])
        return PlainTextResponse(frame.to_csv(index=False), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=cardiolens_history.csv"})

    @router.get("/clinic/patients")
    def patients(staff: User = Depends(need("clinician", "admin")), s: Session = Depends(db)):
        if not staff.clinic:
            return []
        out = []
        for p in s.query(User).filter_by(role="patient", clinic=staff.clinic).order_by(User.name):
            rows = s.query(Assessment).filter_by(patient_id=p.id).order_by(Assessment.id.desc()).all()
            out.append({"id": p.id, "name": p.name, "email": p.email, "assessments": len(rows),
                        "pending_review": sum(a.status == "submitted" for a in rows),
                        "last_assessment": rows[0].created_at.isoformat() if rows else None})
        audit(s, staff, "view_directory")
        return out

    @router.get("/clinic/patients/{pid}/assessments")
    def patient_history(pid: int, staff: User = Depends(need("clinician", "admin")), s: Session = Depends(db)):
        patient = s.get(User, pid)
        if patient is None or patient.role != "patient" or not staff.clinic or patient.clinic != staff.clinic:
            raise HTTPException(404, "Patient not found.")
        audit(s, staff, "view_patient", pid)
        rows = s.query(Assessment).filter_by(patient_id=pid).order_by(Assessment.id.desc()).all()
        return [detail(a) for a in rows]

    @router.post("/clinic/assessments/{aid}/notes", status_code=201)
    def add_note(aid: int, body: NoteIn, staff: User = Depends(need("clinician")), s: Session = Depends(db)):
        a = in_scope(s, staff, aid)
        s.add(Note(assessment_id=a.id, author_id=staff.id, body=body.body.strip()))
        a.status = "reviewed"
        s.commit()
        audit(s, staff, "clinical_note", aid)
        return detail(s.get(Assessment, aid))

    def keep(s, user, name, origin, report):
        report["provenance"] = {"origin": origin,
                                "note": "Synthetic demonstration data, not a real result." if origin == "synthetic_demo"
                                else "New experiment on the uploaded dataset."}
        exp = Experiment(owner_id=user.id, name=name, origin=origin, result=clean(report))
        s.add(exp)
        s.commit()
        audit(s, user, "experiment", exp.id)
        return {"id": exp.id, "name": name, "origin": origin}

    @router.post("/research/experiments", status_code=201)
    def run_experiment(name: str = Form(..., max_length=120), target: str = Form(..., max_length=80),
                       site_col: str = Form(..., max_length=80), dev_site: str = Form(..., max_length=80),
                       group_col: str = Form(default="", max_length=80), file: UploadFile = File(...),
                       user: User = Depends(need("researcher")), s: Session = Depends(db)):
        raw = file.file.read(MAX_UPLOAD + 1)
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, "The file is larger than 10 MB.")
        try:
            frame = pd.read_csv(io.BytesIO(raw))
        except Exception:
            raise HTTPException(422, "The file could not be read as a CSV.")
        if not 60 <= len(frame) <= 200000 or not 3 <= frame.shape[1] <= 200:
            raise HTTPException(422, "The table needs 60 to 200000 rows and 3 to 200 columns.")
        try:
            report = research_engine.analyze(frame, target, site_col, dev_site, group_col or None, name)
        except ValueError as error:
            raise HTTPException(422, str(error))
        return keep(s, user, name, "uploaded", report)

    @router.post("/research/experiments/demo", status_code=201)
    def run_demo(user: User = Depends(need("researcher")), s: Session = Depends(db)):
        frame, cfg = research_demo.synthetic()
        return keep(s, user, cfg["name"], "synthetic_demo", research_engine.analyze(frame, **cfg))

    @router.get("/research/experiments")
    def experiments(user: User = Depends(need("researcher")), s: Session = Depends(db)):
        rows = s.query(Experiment).filter_by(owner_id=user.id).order_by(Experiment.id.desc()).all()
        return [{"id": e.id, "name": e.name, "origin": e.origin, "created_at": e.created_at.isoformat()} for e in rows]

    @router.get("/research/experiments/{eid}")
    def experiment(eid: int, user: User = Depends(need("researcher")), s: Session = Depends(db)):
        e = s.get(Experiment, eid)
        if e is None or e.owner_id != user.id:
            raise HTTPException(404, "Experiment not found.")
        return {"id": e.id, "name": e.name, "origin": e.origin, "result": e.result}

    @router.get("/research/paper-results")
    def paper(user: User = Depends(need("researcher", "clinician", "admin"))):
        card = ctx.engine().card
        real = card["data_source"] == "uci"
        return {"data_source": card["data_source"], "paper_protocol": card.get("paper_protocol"),
                "provenance": "reproduced_from_supplied_data" if real else "synthetic_demo",
                "note": "Historical angiography-referred cohorts; target is obstructive coronary disease, not heart-attack risk."}

    return router
