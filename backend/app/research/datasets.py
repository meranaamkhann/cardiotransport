import hashlib
import io
import re
import uuid
from pathlib import Path
from typing import List, Optional

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator

COLUMN_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_ .\-]{0,63}$")
IDENTIFIER_HINTS = ("name", "email", "phone", "mobile", "address", "ssn", "aadhaar", "aadhar", "passport", "mrn", "dob")
MIN_ROWS, MAX_ROWS, MAX_COLUMNS = 40, 200_000, 200


class ExperimentRequest(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    kind: str = Field(pattern=r"^(paper_replication|custom_validation)$")
    source: str = Field(default="uci", pattern=r"^(uci|synthetic)$")
    recode_zeros: bool = False
    bootstrap: int = Field(default=2000, ge=100, le=2000)
    repeats: int = Field(default=10, ge=1, le=10)
    dataset_id: Optional[int] = None
    target_column: Optional[str] = Field(default=None, max_length=64)
    site_column: Optional[str] = Field(default=None, max_length=64)
    dev_site: Optional[str] = Field(default=None, max_length=64)
    feature_columns: List[str] = Field(default_factory=list, max_length=60)
    group_column: Optional[str] = Field(default=None, max_length=64)
    max_missing: float = Field(default=0.30, ge=0.05, le=0.9)

    @model_validator(mode="after")
    def custom_needs_mapping(self):
        if self.kind == "custom_validation":
            needed = [self.dataset_id, self.target_column, self.site_column, self.dev_site]
            if any(v in (None, "") for v in needed) or not self.feature_columns:
                raise ValueError("Custom validation needs a dataset, target, site column, development site and features.")
        return self


def decode(raw: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig", nrows=MAX_ROWS + 1, skipinitialspace=True)
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(raw), encoding="latin-1", nrows=MAX_ROWS + 1, skipinitialspace=True)
    except (pd.errors.ParserError, pd.errors.EmptyDataError):
        raise ValueError("The file could not be read as a CSV.")


def inspect_csv(raw: bytes, max_bytes: int):
    if len(raw) > max_bytes:
        raise ValueError(f"The file is larger than {max_bytes // 1_000_000} MB.")
    frame = decode(raw)
    frame.columns = [str(c).strip() for c in frame.columns]
    if frame.shape[1] < 2 or frame.shape[1] > MAX_COLUMNS:
        raise ValueError(f"The file must have between 2 and {MAX_COLUMNS} columns.")
    if not (MIN_ROWS <= len(frame) <= MAX_ROWS):
        raise ValueError(f"The file must have between {MIN_ROWS} and {MAX_ROWS} rows.")
    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("Column names must be unique.")
    bad = [c for c in frame.columns if not COLUMN_NAME.match(c)]
    if bad:
        raise ValueError("Unsupported column names (use letters, digits, spaces, dots, dashes and underscores): "
                         + ", ".join(bad[:5]))
    identifiers = [c for c in frame.columns if any(h in c.lower() for h in IDENTIFIER_HINTS)]
    if identifiers:
        raise ValueError("These columns look like direct identifiers; remove them before uploading: "
                         + ", ".join(identifiers))
    info, warnings = [], []
    for c in frame.columns:
        numeric = pd.to_numeric(frame[c], errors="coerce")
        is_numeric = numeric.notna().sum() >= 0.9 * max(frame[c].notna().sum(), 1)
        info.append({"name": c, "kind": "numeric" if is_numeric else "categorical",
                     "missing_pct": round(float(frame[c].isna().mean() * 100), 1), "n_unique": int(frame[c].nunique())})
        if frame[c].nunique() <= 1:
            warnings.append(f"Column {c} is constant.")
    duplicates = int(frame.duplicated().sum())
    if duplicates:
        warnings.append(f"{duplicates} duplicate rows were found.")
    return frame, info, warnings


def store(raw: bytes, upload_dir: Path):
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.csv"
    (upload_dir / name).write_bytes(raw)
    return name, hashlib.sha256(raw).hexdigest()


def load(path: Path) -> pd.DataFrame:
    frame = decode(path.read_bytes())
    frame.columns = [str(c).strip() for c in frame.columns]
    return frame


def prepare(frame: pd.DataFrame, request: ExperimentRequest, info: list):
    columns = {c["name"]: c for c in info}
    for needed in [request.target_column, request.site_column, *request.feature_columns,
                   *([request.group_column] if request.group_column else [])]:
        if needed not in columns:
            raise ValueError(f"Column {needed} is not in the dataset.")
    if request.target_column in request.feature_columns or request.site_column in request.feature_columns:
        raise ValueError("The target and site columns cannot also be features.")
    target = pd.to_numeric(frame[request.target_column], errors="coerce")
    data = pd.DataFrame({"target": (target > 0).astype(int), "site": frame[request.site_column].astype(str)})
    data = data[target.notna().values].copy()
    types = {}
    for feature in request.feature_columns:
        if columns[feature]["kind"] == "numeric" and columns[feature]["n_unique"] > 5:
            data[feature] = pd.to_numeric(frame.loc[data.index, feature], errors="coerce")
            types[feature] = "numeric"
        else:
            if columns[feature]["n_unique"] > 20:
                raise ValueError(f"Column {feature} has too many distinct categories (more than 20).")
            values = frame.loc[data.index, feature]
            data[feature] = pd.to_numeric(values, errors="coerce") if columns[feature]["kind"] == "numeric" else values.astype(object)
            types[feature] = "categorical"
    if request.group_column:
        data["group"] = frame.loc[data.index, request.group_column].astype(str)
    sites = data["site"].value_counts()
    if request.dev_site not in sites.index:
        raise ValueError("The development site was not found in the site column.")
    dev = data[data["site"] == request.dev_site]
    if len(dev) < 60 or dev["target"].sum() < 10 or (len(dev) - dev["target"].sum()) < 10:
        raise ValueError("The development site needs at least 60 rows, with at least 10 of each outcome.")
    others = [s for s in sites.index if s != request.dev_site and sites[s] >= 20]
    if not others:
        raise ValueError("At least one other site with 20 or more rows is needed for external validation.")
    data = data[data["site"].isin([request.dev_site, *others])].reset_index(drop=True)
    return data, types
