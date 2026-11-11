from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from ..db.models import AuditEvent, User
from .ratelimit import client_ip


def record(db: Session, actor: Optional[User], action: str, entity: str, entity_id: Optional[int] = None,
           request: Optional[Request] = None, detail: Optional[dict] = None, clinic_id: Optional[int] = None):
    db.add(AuditEvent(actor_id=actor.id if actor else None,
                      clinic_id=clinic_id if clinic_id is not None else (actor.clinic_id if actor else None),
                      action=action, entity=entity, entity_id=entity_id,
                      ip=client_ip(request) if request else None, detail=detail))
