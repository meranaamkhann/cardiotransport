import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import audit
from ..core.deps import current_user, require
from ..core.ratelimit import rate_limit
from ..core.security import create_token, hash_password, verify_password
from ..db.base import get_db
from ..db.models import Clinic, PatientProfile, Role, User
from ..schemas import ClinicRegistration, Credentials, JoinClinic, Registration
from .common import user_out

router = APIRouter(prefix="/auth", tags=["auth"])
MAX_FAILED = 5
LOCK_MINUTES = 15


def check_password(password: str):
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(422, "Password must contain at least one letter and one digit.")


def new_code(db: Session) -> str:
    while True:
        code = secrets.token_hex(3).upper()
        if db.scalar(select(Clinic).where(Clinic.code == code)) is None:
            return code


def issue(user: User) -> dict:
    return {"access_token": create_token(user.id, user.role), "token_type": "bearer", "user": user_out(user)}


def normalise(email: str) -> str:
    return email.strip().lower()


@router.post("/register", status_code=201, dependencies=[Depends(rate_limit("register", 10, 3600))])
def register(payload: Registration, request: Request, db: Session = Depends(get_db)):
    check_password(payload.password)
    email = normalise(payload.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    clinic = None
    if payload.clinic_code:
        clinic = db.scalar(select(Clinic).where(Clinic.code == payload.clinic_code.strip().upper()))
        if clinic is None:
            raise HTTPException(404, "That clinic code was not recognised.")
    user = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name.strip(),
                role=Role.patient.value, clinic_id=clinic.id if clinic else None)
    user.profile = PatientProfile()
    db.add(user)
    db.flush()
    audit.record(db, user, "register", "user", user.id, request)
    db.commit()
    return issue(user)


@router.post("/register-clinic", status_code=201, dependencies=[Depends(rate_limit("register-clinic", 5, 3600))])
def register_clinic(payload: ClinicRegistration, request: Request, db: Session = Depends(get_db)):
    check_password(payload.password)
    email = normalise(payload.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    clinic = Clinic(name=payload.clinic_name.strip(), code=new_code(db))
    db.add(clinic)
    db.flush()
    user = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name.strip(),
                role=Role.clinic_admin.value, clinic_id=clinic.id)
    db.add(user)
    db.flush()
    audit.record(db, user, "register_clinic", "clinic", clinic.id, request)
    db.commit()
    return issue(user)


@router.post("/login", dependencies=[Depends(rate_limit("login", 15, 60))])
def login(payload: Credentials, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == normalise(payload.email)))
    now = datetime.now(timezone.utc)
    if user is not None and user.locked_until is not None:
        locked = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
        if locked > now:
            raise HTTPException(423, "Too many failed attempts. Try again in a few minutes.")
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        if user is not None:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED:
                user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
                user.failed_logins = 0
            audit.record(db, user, "login_failed", "user", user.id, request)
            db.commit()
        raise HTTPException(401, "Incorrect email or password.")
    user.failed_logins, user.locked_until = 0, None
    audit.record(db, user, "login", "user", user.id, request)
    db.commit()
    return issue(user)


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


@router.post("/join-clinic")
def join_clinic(payload: JoinClinic, request: Request, user: User = Depends(require("patient")),
                db: Session = Depends(get_db)):
    clinic = db.scalar(select(Clinic).where(Clinic.code == payload.code.strip().upper()))
    if clinic is None:
        raise HTTPException(404, "That clinic code was not recognised.")
    user.clinic_id = clinic.id
    audit.record(db, user, "consent_share_with_clinic", "clinic", clinic.id, request)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.post("/leave-clinic")
def leave_clinic(request: Request, user: User = Depends(require("patient")), db: Session = Depends(get_db)):
    previous = user.clinic_id
    user.clinic_id = None
    audit.record(db, user, "consent_withdrawn", "clinic", previous, request, clinic_id=previous)
    db.commit()
    db.refresh(user)
    return user_out(user)
