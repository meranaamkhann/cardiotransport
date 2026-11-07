import io
import urllib.request

import numpy as np
import pandas as pd

from .config import DATA_DIR
from .features import SITES

COLUMNS = ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg", "thalach",
           "exang", "oldpeak", "slope", "ca", "thal", "num"]
FILES = {"Cleveland": "cleveland", "Hungary": "hungarian", "Switzerland": "switzerland", "Long Beach VA": "va"}
MIRRORS = [
    "https://archive.ics.uci.edu/ml/machine-learning-databases/heart-disease/processed.{}.data",
    "https://huggingface.co/datasets/mstz/heart/resolve/main/processed.{}.data",
]


def fetch(site):
    path = DATA_DIR / f"processed.{FILES[site]}.data"
    if path.exists():
        return path.read_text(encoding="latin-1")
    for template in MIRRORS:
        try:
            with urllib.request.urlopen(template.format(FILES[site]), timeout=25) as response:
                text = response.read().decode("latin-1")
        except Exception:
            continue
        if text.count("\n") > 50:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="latin-1")
            return text
    return None


def parse(text, site):
    frame = pd.read_csv(io.StringIO(text), header=None, names=COLUMNS, na_values=["?"], skipinitialspace=True)
    frame = frame.apply(pd.to_numeric, errors="coerce")
    frame["site"] = site
    return frame


def zero_counts(frame):
    out = {}
    for site, part in frame.groupby("site"):
        out[site] = {"chol": int((part["chol"] == 0).sum()), "trestbps": int((part["trestbps"] == 0).sum()),
                     "n": int(len(part))}
    return out


def clean(frame):
    frame = frame.copy()
    frame.loc[frame["chol"] <= 0, "chol"] = np.nan
    frame.loc[frame["trestbps"] <= 0, "trestbps"] = np.nan
    frame["target"] = (frame["num"] > 0).astype(int)
    return frame.reset_index(drop=True)


def synthetic(seed=11):
    rng = np.random.default_rng(seed)
    spec = {
        "Cleveland": (303, -0.3, 0.0, 0.01, 0.0),
        "Hungary": (294, -1.1, 0.12, 0.95, 0.05),
        "Switzerland": (123, 2.4, 0.9, 0.96, 0.6),
        "Long Beach VA": (200, 1.0, 0.55, 0.97, 0.15),
    }
    frames = []
    for site, (n, shift, chol_zero, deep_missing, other_missing) in spec.items():
        age = np.clip(rng.normal(54, 9, n), 29, 77).round()
        sex = rng.binomial(1, 0.72 if site != "Cleveland" else 0.68, n).astype(float)
        cp = rng.choice([1, 2, 3, 4], n, p=[0.08, 0.17, 0.28, 0.47]).astype(float)
        trestbps = np.clip(rng.normal(131, 17, n), 90, 200).round()
        chol = np.clip(rng.normal(246, 50, n), 125, 560).round()
        fbs = rng.binomial(1, 0.15, n).astype(float)
        restecg = rng.choice([0, 1, 2], n, p=[0.5, 0.02, 0.48]).astype(float)
        exang = rng.binomial(1, 0.33, n).astype(float)
        thalach = np.clip(rng.normal(150, 22, n) - 0.5 * (age - 54), 75, 202).round()
        oldpeak = np.round(np.clip(rng.gamma(1.1, 0.9, n), 0, 6.2), 1)
        slope = rng.choice([1, 2, 3], n, p=[0.45, 0.45, 0.1]).astype(float)
        ca = rng.choice([0, 1, 2, 3], n, p=[0.55, 0.22, 0.15, 0.08]).astype(float)
        thal = rng.choice([3, 6, 7], n, p=[0.55, 0.06, 0.39]).astype(float)
        lp = (-4.0 + 0.035 * (age - 54) + 1.1 * sex + 1.35 * (cp == 4) - 0.3 * (cp == 3) + 0.4 * exang
              + 0.5 * oldpeak - 0.02 * (thalach - 150) + 0.006 * (trestbps - 131) + 0.004 * (chol - 246) + shift)
        y = rng.random(n) < 1 / (1 + np.exp(-lp))
        frame = pd.DataFrame(dict(age=age, sex=sex, cp=cp, trestbps=trestbps, chol=chol, fbs=fbs, restecg=restecg,
                                  thalach=thalach, exang=exang, oldpeak=oldpeak, slope=slope, ca=ca, thal=thal))
        frame["num"] = np.where(y, rng.integers(1, 5, n), 0)
        frame.loc[rng.random(n) < chol_zero, "chol"] = 0
        for col in ("ca", "thal"):
            frame.loc[rng.random(n) < deep_missing, col] = np.nan
        for col in ("slope", "fbs", "thalach", "oldpeak", "exang", "restecg"):
            frame.loc[rng.random(n) < other_missing * 0.5, col] = np.nan
        frame["site"] = site
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def load_cohorts(require_real=False, force_synthetic=False):
    if not force_synthetic:
        frames = []
        for site in SITES:
            text = fetch(site)
            if text is None:
                break
            frames.append(parse(text, site))
        else:
            raw = pd.concat(frames, ignore_index=True)
            return clean(raw), "uci", zero_counts(raw)
        if require_real:
            raise RuntimeError("UCI Heart Disease files could not be found or downloaded. Place the four "
                               "processed.*.data files in backend/data/raw and run again.")
    raw = synthetic()
    return clean(raw), "synthetic", zero_counts(raw)
