import io

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import RepeatedStratifiedKFold

from .config import SEED
from .features import CLINICAL, CORE, DEPLOY

TEMPLATE_COLUMNS = CLINICAL + ["outcome"]
MIN_ROWS = 40
MIN_PER_CLASS = 10
SLOPE_MIN_ROWS = 100
SLOPE_MIN_PER_CLASS = 25


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def template_csv():
    sample = pd.DataFrame([
        [58, 1, 4, 1, 140, 230, 0, 1, 130, 1.5, 1],
        [46, 0, 3, 0, 118, 190, 0, 0, 165, 0.0, 0],
    ], columns=TEMPLATE_COLUMNS)
    return sample.to_csv(index=False)


def fit_intercept(y, z):
    return float(sm.GLM(y, np.ones((len(z), 1)), family=sm.families.Binomial(), offset=z).fit().params[0])


def fit_slope(y, z):
    params = sm.Logit(y, sm.add_constant(z)).fit(disp=0).params
    return float(params[0]), float(params[1])


def parse_upload(raw: bytes):
    if len(raw) > 2_000_000:
        raise ValueError("The file is larger than 2 MB.")
    frame = pd.read_csv(io.BytesIO(raw))
    frame.columns = [c.strip().lower() for c in frame.columns]
    missing = [c for c in CORE + ["outcome"] if c not in frame.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    for c in frame.columns:
        frame[c] = pd.to_numeric(frame[c], errors="coerce")
    frame = frame[frame["outcome"].isin([0, 1])].reset_index(drop=True)
    for c in ("chol", "trestbps"):
        frame.loc[frame[c] <= 0, c] = np.nan
    return frame


def calibrate_tier(engine, frame, tier):
    features = DEPLOY[tier]
    pipe = engine.pipelines[tier]
    y = frame["outcome"].values.astype(int)
    base = pipe.predict_proba(frame[features])[:, 1]
    z = logit(base)
    allow_slope = bool(len(y) >= SLOPE_MIN_ROWS and min(y.sum(), (1 - y).sum()) >= SLOPE_MIN_PER_CLASS)

    methods = ["none", "intercept"] + (["slope"] if allow_slope else [])
    oof = {m: np.zeros(len(y)) for m in methods}
    count = np.zeros(len(y))
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=6, random_state=SEED)
    for train, test in cv.split(z.reshape(-1, 1), y):
        oof["none"][test] += sigmoid(z[test])
        oof["intercept"][test] += sigmoid(z[test] + fit_intercept(y[train], z[train]))
        if allow_slope:
            a, b = fit_slope(y[train], z[train])
            oof["slope"][test] += sigmoid(a + b * z[test])
        count[test] += 1
    brier = {m: float(brier_score_loss(y, oof[m] / count)) for m in methods}
    chosen = "intercept"
    if allow_slope and brier["slope"] < brier["intercept"] * 0.98:
        chosen = "slope"

    if chosen == "slope":
        intercept, slope = fit_slope(y, z)
    else:
        intercept, slope = fit_intercept(y, z), 1.0
    try:
        cal_slope = fit_slope(y, z)[1]
        cal_intercept = fit_intercept(y, z)
    except Exception:
        cal_slope, cal_intercept = None, None
    return {
        "tier": tier,
        "method": chosen,
        "intercept": round(intercept, 4),
        "slope": round(slope, 4),
        "n": int(len(y)),
        "events": int(y.sum()),
        "observed_rate": round(float(y.mean()), 3),
        "mean_predicted_before": round(float(base.mean()), 3),
        "calibration_intercept_before": None if cal_intercept is None else round(cal_intercept, 3),
        "calibration_slope_before": None if cal_slope is None else round(cal_slope, 3),
        "brier_before": round(brier["none"], 4),
        "brier_after": round(brier[chosen], 4),
        "slope_update_considered": allow_slope,
    }


def calibrate(engine, raw: bytes):
    frame = parse_upload(raw)
    n, events = len(frame), int(frame["outcome"].sum())
    if n < MIN_ROWS or min(events, n - events) < MIN_PER_CLASS:
        raise ValueError(f"Need at least {MIN_ROWS} labelled rows with at least {MIN_PER_CLASS} cases and "
                         f"{MIN_PER_CLASS} non-cases; the file has {n} rows and {events} cases.")
    tiers = ["core"]
    if all(c in frame.columns for c in ("restecg", "thalach", "oldpeak")) and \
            frame[["restecg", "thalach", "oldpeak"]].notna().all(axis=1).mean() >= 0.8:
        tiers.append("clinical")
    return {"n": n, "events": events, "results": [calibrate_tier(engine, frame, t) for t in tiers]}
