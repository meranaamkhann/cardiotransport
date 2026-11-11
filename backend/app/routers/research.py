from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import data as data_module
from ..config import get_settings
from ..core import audit
from ..core.deps import require
from ..db.base import get_db
from ..db.models import Dataset, Experiment, ModelVersion, Report, User
from ..research import datasets, jobs
from ..services import reports

router = APIRouter(prefix="/research", tags=["research"], dependencies=[Depends(require("researcher"))])
researcher = Depends(require("researcher"))
MAX_ACTIVE = 3


def dataset_out(d: Dataset) -> dict:
    return {"id": d.id, "name": d.name, "n_rows": d.n_rows, "columns": d.columns, "sha256": d.sha256, "created_at": d.created_at.isoformat()}


def experiment_out(e: Experiment, detail: bool = False) -> dict:
    body = {"id": e.id, "name": e.name, "kind": e.kind, "provenance": e.provenance, "status": e.status, "progress": e.progress,
            "stage": e.stage, "dataset_id": e.dataset_id, "error": e.error, "created_at": e.created_at.isoformat(),
            "finished_at": e.finished_at.isoformat() if e.finished_at else None}
    if detail:
        body.update({"config": e.config, "result": e.result})
    return body


def owned_experiment(db: Session, user: User, experiment_id: int) -> Experiment:
    row = db.scalar(select(Experiment).where(Experiment.id == experiment_id, Experiment.owner_id == user.id))
    if row is None:
        raise HTTPException(404, "Experiment not found")
    return row


@router.get("/models")
def models(db: Session = Depends(get_db)):
    rows = db.scalars(select(ModelVersion).order_by(ModelVersion.trained_at.desc())).all()
    return [{"id": m.id, "tag": m.tag, "version": m.version, "data_source": m.data_source, "trained_at": m.trained_at.isoformat(),
             "is_active": m.is_active, "card": m.card} for m in rows]


@router.get("/uci-status")
def uci_status():
    present = data_module.available_locally()
    return {"available": present, "missing": [s for s in data_module.SITES if s not in present],
            "note": "Missing files are downloaded when a UCI experiment starts, if the server can reach the internet."}


@router.post("/datasets", status_code=201)
async def upload_dataset(request: Request, file: UploadFile = File(...), name: str = Form(min_length=3, max_length=120),
                         user: User = researcher, db: Session = Depends(get_db)):
    settings = get_settings()
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(422, "Only .csv files are accepted.")
    raw = await file.read(settings.max_upload_mb * 1_000_000 + 1)
    try:
        frame, info, warnings = datasets.inspect_csv(raw, settings.max_upload_mb * 1_000_000)
    except ValueError as error:
        raise HTTPException(422, str(error))
    filename, digest = datasets.store(raw, settings.upload_dir)
    row = Dataset(owner_id=user.id, name=name.strip(), filename=filename, sha256=digest, n_rows=len(frame), columns=info)
    db.add(row)
    db.flush()
    audit.record(db, user, "dataset_uploaded", "dataset", row.id, request, {"rows": len(frame)})
    db.commit()
    return {**dataset_out(row), "warnings": warnings}


@router.get("/datasets")
def list_datasets(user: User = researcher, db: Session = Depends(get_db)):
    rows = db.scalars(select(Dataset).where(Dataset.owner_id == user.id).order_by(Dataset.created_at.desc())).all()
    return [dataset_out(d) for d in rows]


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int, request: Request, user: User = researcher, db: Session = Depends(get_db)):
    row = db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.owner_id == user.id))
    if row is None:
        raise HTTPException(404, "Dataset not found")
    (get_settings().upload_dir / row.filename).unlink(missing_ok=True)
    audit.record(db, user, "dataset_deleted", "dataset", row.id, request)
    db.delete(row)
    db.commit()


@router.post("/experiments", status_code=202)
def create_experiment(payload: datasets.ExperimentRequest, request: Request, background: BackgroundTasks,
                      user: User = researcher, db: Session = Depends(get_db)):
    active = db.scalar(select(func.count()).select_from(Experiment).where(Experiment.owner_id == user.id, Experiment.status.in_(["queued", "running"])))
    if active >= MAX_ACTIVE:
        raise HTTPException(429, "You already have several experiments running. Wait for one to finish.")
    config = payload.model_dump()
    if payload.kind == "custom_validation":
        dataset = db.scalar(select(Dataset).where(Dataset.id == payload.dataset_id, Dataset.owner_id == user.id))
        if dataset is None:
            raise HTTPException(404, "Dataset not found")
        try:
            datasets.prepare(datasets.load(Path(get_settings().upload_dir) / dataset.filename), payload, dataset.columns)
        except ValueError as error:
            raise HTTPException(422, str(error))
    row = Experiment(owner_id=user.id, dataset_id=payload.dataset_id, name=payload.name.strip(), kind=payload.kind,
                     provenance=jobs.provenance_for(config), config=config)
    db.add(row)
    db.flush()
    audit.record(db, user, "experiment_created", "experiment", row.id, request, {"kind": payload.kind})
    db.commit()
    background.add_task(jobs.execute, row.id)
    return experiment_out(row)


@router.get("/experiments")
def list_experiments(user: User = researcher, db: Session = Depends(get_db)):
    rows = db.scalars(select(Experiment).where(Experiment.owner_id == user.id).order_by(Experiment.created_at.desc()).limit(100)).all()
    return [experiment_out(e) for e in rows]


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: int, user: User = researcher, db: Session = Depends(get_db)):
    return experiment_out(owned_experiment(db, user, experiment_id), detail=True)


@router.delete("/experiments/{experiment_id}", status_code=204)
def delete_experiment(experiment_id: int, user: User = researcher, db: Session = Depends(get_db)):
    row = owned_experiment(db, user, experiment_id)
    if row.status in ("queued", "running"):
        raise HTTPException(409, "Wait for the experiment to finish before deleting it.")
    db.query(Report).filter(Report.experiment_id == row.id).delete()
    db.delete(row)
    db.commit()


def finished(db: Session, user: User, experiment_id: int) -> Experiment:
    row = owned_experiment(db, user, experiment_id)
    if row.status != "completed":
        raise HTTPException(409, "The experiment has not completed.")
    return row


@router.get("/experiments/{experiment_id}/report.pdf")
def experiment_report(experiment_id: int, request: Request, user: User = researcher, db: Session = Depends(get_db)):
    row = finished(db, user, experiment_id)
    pdf = reports.experiment_pdf(row, user.full_name)
    db.add(Report(experiment_id=row.id, created_by=user.id, kind="research", sha256=reports.sha(pdf)))
    audit.record(db, user, "report_generated", "experiment", row.id, request)
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="cardiolens-experiment-{row.id}.pdf"'})


@router.get("/experiments/{experiment_id}/report.csv")
def experiment_csv(experiment_id: int, user: User = researcher, db: Session = Depends(get_db)):
    row = finished(db, user, experiment_id)
    return Response(reports.experiment_csv(row), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="cardiolens-experiment-{row.id}.csv"'})
