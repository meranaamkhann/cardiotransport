import logging
import os
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import text
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import clinic
from .config import ARTIFACT_DIR, DATABASE_URL, SECRET_KEY, STATIC_DIR, TOKEN_MINUTES
from .db import Base, connect
from .engine import Engine
from .models import User
from .platform import Limiter, build_router
from .schemas import Assessment, Wellness
from .security import hash_password
from .wellness import assess_wellness


def create_app(artifact_dir: Path = ARTIFACT_DIR, static_dir: Path = STATIC_DIR, db_url: str = DATABASE_URL,
               secret: str = SECRET_KEY, admin=None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}')
    app = FastAPI(title="CardioLens", version="2.0.0")
    db_engine, Session = connect(db_url)
    Base.metadata.create_all(db_engine)
    admin = admin or (os.environ.get("CARDIOLENS_ADMIN_EMAIL"), os.environ.get("CARDIOLENS_ADMIN_PASSWORD"),
                      os.environ.get("CARDIOLENS_CLINIC", "main"))
    if admin[0] and admin[1]:
        with Session() as s:
            if not s.query(User).filter_by(email=admin[0].lower()).first():
                s.add(User(email=admin[0].lower(), name="Administrator", role="admin", clinic=admin[2],
                           password_hash=hash_password(admin[1])))
                s.commit()
    state = {"engine": None}

    def engine() -> Engine:
        if state["engine"] is None:
            try:
                state["engine"] = Engine(artifact_dir)
            except FileNotFoundError:
                raise HTTPException(503, "The model has not been trained yet. Run: python -m app.training")
        return state["engine"]

    app.include_router(build_router(SimpleNamespace(Session=Session, secret=secret, token_minutes=TOKEN_MINUTES,
                                                    engine=engine, limiter=Limiter(10, 60))))

    @app.get("/api/health")
    def health():
        ready = (artifact_dir / "models.joblib").exists() and (artifact_dir / "model_card.json").exists()
        try:
            with Session() as s:
                s.execute(text("select 1"))
            database = "ok"
        except Exception:
            database = "down"
        return {"status": "ok" if ready and database == "ok" else "degraded", "model": ready, "database": database}

    @app.get("/api/model-card")
    def model_card():
        return engine().card

    @app.post("/api/assess")
    def assess(payload: Assessment):
        return engine().assess(payload)

    @app.post("/api/wellness")
    def wellness(payload: Wellness):
        return assess_wellness(payload)

    @app.get("/api/clinic/template", response_class=PlainTextResponse)
    def template():
        return PlainTextResponse(clinic.template_csv(), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=cardiolens_template.csv"})

    @app.post("/api/clinic/calibrate")
    async def calibrate(file: UploadFile = File(...), site_name: str = Form(default="")):
        raw = await file.read()
        try:
            result = clinic.calibrate(engine(), raw)
        except ValueError as error:
            raise HTTPException(422, str(error))
        result["site_name"] = site_name.strip()[:80]
        return result

    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}")
        def spa(path: str):
            target = (static_dir / path).resolve()
            if path and target.is_file() and static_dir.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
