import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .core import logging as log_setup
from .db.base import Base, SessionLocal, engine as db_engine
from .engine import Engine
from .routers import admin, auth, clinician, patient, public, research
from .services import registry

log = logging.getLogger("cardiolens")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'",
}


def load_engine(artifact_dir: Path) -> Optional[Engine]:
    try:
        engine = Engine(artifact_dir)
    except FileNotFoundError:
        log.warning("model artifacts not found in %s", artifact_dir)
        return None
    with SessionLocal() as db:
        registry.sync(db, engine.card)
    return engine


def create_app(artifact_dir: Optional[Path] = None, static_dir: Optional[Path] = None, create_tables: bool = False) -> FastAPI:
    settings = get_settings()
    artifact_dir = artifact_dir or settings.artifact_dir
    static_dir = static_dir or settings.static_dir

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        log_setup.configure()
        if create_tables or settings.is_sqlite:
            Base.metadata.create_all(db_engine)
        app.state.engine = load_engine(artifact_dir)
        yield

    app = FastAPI(title="CardioLens API", version="2.0.0", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.engine = None
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def observe(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error", extra={"method": request.method, "path": request.url.path})
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        if request.url.path.startswith("/api") and request.url.path != "/api/health":
            log.info("request", extra={"method": request.method, "path": request.url.path, "status": response.status_code,
                                       "duration_ms": round((time.perf_counter() - started) * 1000, 1)})
        return response

    for module in (public, auth, patient, clinician, admin, research):
        app.include_router(module.router, prefix="/api")

    if static_dir.exists() and (static_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            target = (static_dir / path).resolve()
            if path and target.is_file() and static_dir.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
