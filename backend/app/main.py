from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import clinic
from .config import ARTIFACT_DIR, STATIC_DIR
from .engine import Engine
from .schemas import Assessment, Wellness
from .wellness import assess_wellness


def create_app(artifact_dir: Path = ARTIFACT_DIR, static_dir: Path = STATIC_DIR) -> FastAPI:
    app = FastAPI(title="CardioLens", version="1.0.0")
    state = {"engine": None}

    def engine() -> Engine:
        if state["engine"] is None:
            try:
                state["engine"] = Engine(artifact_dir)
            except FileNotFoundError:
                raise HTTPException(503, "The model has not been trained yet. Run: python -m app.training")
        return state["engine"]

    @app.get("/api/health")
    def health():
        ready = (artifact_dir / "models.joblib").exists() and (artifact_dir / "model_card.json").exists()
        return {"status": "ok" if ready else "model_missing"}

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
