from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.ratelimit import rate_limit
from ..db.base import get_db
from ..schemas import Assessment, Wellness
from ..wellness import assess_wellness
from .common import get_engine

router = APIRouter(tags=["public"])
limit = Depends(rate_limit("public", 40, 60))


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "database unavailable")
    if request.app.state.engine is None:
        raise HTTPException(503, "model not trained")
    return {"status": "ready", "model": request.app.state.engine.card["version"]}


@router.get("/model-card")
def model_card(request: Request):
    return get_engine(request).card


@router.post("/public/assess", dependencies=[limit])
def public_assess(payload: Assessment, request: Request):
    return get_engine(request).assess(payload)


@router.post("/public/wellness", dependencies=[limit])
def public_wellness(payload: Wellness):
    return assess_wellness(payload)
