import logging
import threading
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import data as data_module
from ..config import get_settings
from ..db.base import SessionLocal
from ..db.models import Dataset, Experiment
from ..features import CATEGORICAL, CLINICAL, FULL, NUMERIC
from . import datasets, paper
from .engine import run_validation

log = logging.getLogger("cardiolens.research")
_slot = threading.Semaphore(1)

PROVENANCE_LABELS = {
    "reproduced": "Reproduction of the paper protocol on the original UCI records",
    "new_experiment": "New experiment (not a result reported in the paper)",
    "synthetic_demo": "Synthetic demonstration (generated data, not real patients)",
}


def provenance_for(config: dict) -> str:
    if config["source"] == "synthetic" and config["kind"] == "paper_replication":
        return "synthetic_demo"
    if config["kind"] == "paper_replication" and not config["recode_zeros"]:
        return "reproduced"
    return "new_experiment"


def update(db: Session, exp: Experiment, fraction: float, stage: str):
    exp.progress, exp.stage = round(fraction, 3), stage[:120]
    db.commit()


def paper_inputs(config: dict):
    frame, source, _ = data_module.load_cohorts(require_real=config["source"] == "uci",
                                                force_synthetic=config["source"] == "synthetic",
                                                recode_zeros=config["recode_zeros"])
    types = {f: "numeric" if f in NUMERIC else "categorical" for f in FULL}
    specs = {"full_logistic": (FULL, "logistic"), "portable_logistic": (CLINICAL, "logistic"),
             "full_forest": (FULL, "forest"), "portable_forest": (CLINICAL, "forest")}
    return frame, specs, types, "Cleveland", None, source


def custom_inputs(db: Session, config: dict):
    dataset = db.get(Dataset, config["dataset_id"])
    if dataset is None:
        raise ValueError("The dataset no longer exists.")
    frame = datasets.load(get_settings().upload_dir / dataset.filename)
    request = datasets.ExperimentRequest(**config)
    prepared, types = datasets.prepare(frame, request, dataset.columns)
    features = request.feature_columns
    ext_sites = [s for s in prepared["site"].unique() if s != request.dev_site]
    portable = [f for f in features if all(prepared.loc[prepared["site"] == s, f].isna().mean() <= request.max_missing
                                           for s in [request.dev_site, *ext_sites])]
    specs = {"full_logistic": (features, "logistic"), "full_forest": (features, "forest")}
    if portable:
        specs = {"full_logistic": (features, "logistic"), "portable_logistic": (portable, "logistic"),
                 "full_forest": (features, "forest"), "portable_forest": (portable, "forest")}
    return prepared, specs, types, request.dev_site, "group" if request.group_column else None, dataset.name


def execute(experiment_id: int):
    with SessionLocal() as db:
        exp = db.get(Experiment, experiment_id)
        if exp is None:
            return
        config = exp.config
        with _slot:
            exp.status = "running"
            update(db, exp, 0.01, "Preparing data")
            try:
                if exp.kind == "paper_replication":
                    frame, specs, types, dev_site, group, source = paper_inputs(config)
                    if group is None:
                        frame["group"] = frame["sex"].map({0.0: "female", 1.0: "male"})
                        group = "group"
                else:
                    frame, specs, types, dev_site, group, source = custom_inputs(db, config)
                result = run_validation(frame, specs, types, dev_site, folds=5, repeats=config["repeats"],
                                        bootstrap=config["bootstrap"], group_column=group,
                                        max_missing=config["max_missing"],
                                        progress=lambda f, m: update(db, exp, f, m))
                result["meta"] = {
                    "name": exp.name, "kind": exp.kind, "provenance": exp.provenance,
                    "provenance_label": PROVENANCE_LABELS[exp.provenance], "data_source": source,
                    "dev_site": dev_site, "recode_zeros": config["recode_zeros"], "bootstrap": config["bootstrap"],
                    "folds": 5, "repeats": config["repeats"], "seed": 20260904, "extension_analyses": [
                        "Decision curve analysis", "Recalibration experiments", "Permutation importance"]}
                notes = ["Decision curve analysis, recalibration experiments and permutation importance are additional analyses that the paper did not report."]
                if exp.kind == "paper_replication":
                    result["comparison_with_paper"] = paper.compare(result["models"])
                    notes.append("Small differences from the paper can come from library versions and random number streams.")
                    if config["recode_zeros"]:
                        notes.append("Zero cholesterol and zero blood pressure values were recoded as missing, which the paper did not do, so this run is a corrected analysis rather than a reproduction.")
                    elif config["source"] == "uci":
                        notes.append("Zero cholesterol values were kept as recorded to match the published protocol.")
                else:
                    notes.append("Cohort data came from a user upload; results describe that dataset only.")
                if config["source"] == "synthetic":
                    notes.append("Synthetic data was used, so none of these numbers describe real patients.")
                result["notes"] = notes
                exp.result, exp.status, exp.progress, exp.stage = result, "completed", 1.0, "Completed"
            except (ValueError, RuntimeError) as error:
                exp.status, exp.error, exp.stage = "failed", str(error)[:500], "Failed"
            except Exception:
                log.exception("experiment %s failed", experiment_id)
                exp.status, exp.error, exp.stage = "failed", "The experiment failed unexpectedly. Check the server logs.", "Failed"
            exp.finished_at = datetime.now(timezone.utc)
            db.commit()
