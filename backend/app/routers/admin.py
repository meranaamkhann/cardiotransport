from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core import audit
from ..core.deps import require
from ..core.security import hash_password
from ..db.base import get_db
from ..db.models import AuditEvent, User
from ..schemas import StaffCreate
from .auth import check_password, normalise

router = APIRouter(prefix="/admin", tags=["admin"])
admin = Depends(require("clinic_admin"))


def staff_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role, "is_active": u.is_active}


@router.get("/users")
def users(user: User = admin, db: Session = Depends(get_db)):
    rows = db.scalars(select(User).where(User.clinic_id == user.clinic_id, User.role != "patient").order_by(User.full_name)).all()
    return [staff_out(u) for u in rows]


@router.post("/users", status_code=201)
def create_user(payload: StaffCreate, request: Request, user: User = admin, db: Session = Depends(get_db)):
    check_password(payload.password)
    email = normalise(payload.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    created = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name.strip(),
                   role=payload.role, clinic_id=user.clinic_id)
    db.add(created)
    db.flush()
    audit.record(db, user, "staff_created", "user", created.id, request, {"role": payload.role})
    db.commit()
    return staff_out(created)


@router.patch("/users/{user_id}/active")
def set_active(user_id: int, active: bool, request: Request, user: User = admin, db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if target is None or target.clinic_id != user.clinic_id or target.role == "patient":
        raise HTTPException(404, "User not found")
    if target.id == user.id:
        raise HTTPException(422, "You cannot deactivate your own account.")
    target.is_active = active
    audit.record(db, user, "staff_activated" if active else "staff_deactivated", "user", target.id, request)
    db.commit()
    return staff_out(target)


@router.get("/audit")
def audit_log(user: User = admin, db: Session = Depends(get_db), limit: int = 100):
    rows = db.scalars(select(AuditEvent).where(AuditEvent.clinic_id == user.clinic_id).order_by(AuditEvent.created_at.desc()).limit(min(limit, 500))).all()
    names = {u.id: u.full_name for u in db.scalars(select(User).where(User.clinic_id == user.clinic_id))}
    return [{"id": e.id, "actor": names.get(e.actor_id, "unknown"), "action": e.action, "entity": e.entity, "entity_id": e.entity_id,
             "created_at": e.created_at.isoformat()} for e in rows]
