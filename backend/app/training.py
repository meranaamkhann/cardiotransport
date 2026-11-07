import argparse
import json
import math
import os
import warnings
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
import sklearn
import statsmodels.api as sm
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegressionCV
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import data
from .config import ARTIFACT_DIR, MODEL_VERSION, SEED
from .features import CATEGORICAL, DEPLOY, NUMERIC, PAPER, SITES

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", module="statsmodels")


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def rnd(value, digits=3):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def build(features, kind):
    numeric = [f for f in features if f in NUMERIC]
    categorical = [f for f in features if f in CATEGORICAL]
    pre = ColumnTransformer(
        [("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), numeric),
         ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                           ("oh", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), categorical)],
        sparse_threshold=0)
    if kind == "logistic":
        clf = LogisticRegressionCV(Cs=[0.05, 0.1, 0.3, 1.0, 3.0],
                                   cv=StratifiedKFold(5, shuffle=True, random_state=SEED),
                                   scoring="neg_log_loss", max_iter=5000)
    else:
        clf = RandomForestClassifier(n_estimators=500, max_depth=5, min_samples_leaf=5, max_features="sqrt",
                                     random_state=SEED, n_jobs=-1)
    return Pipeline([("pre", pre), ("clf", clf)])


def fit(frame, features, kind):
    return build(features, kind).fit(frame[features], frame["target"])


def calibration_terms(y, p):
    z = logit(p)
    try:
        slope = sm.Logit(y, sm.add_constant(z)).fit(disp=0).params[1]
        intercept = sm.GLM(y, np.ones((len(z), 1)), family=sm.families.Binomial(), offset=z).fit().params[0]
        return float(intercept), float(slope)
    except Exception:
        return None, None


def summarize(y, p, rng, boot=400):
    y, p = np.asarray(y).astype(int), np.asarray(p, dtype=float)
    two = len(set(y)) == 2
    predicted = p >= 0.5
    tp = int((predicted & (y == 1)).sum())
    tn = int((~predicted & (y == 0)).sum())
    out = {"n": int(len(y)), "events": int(y.sum()), "prevalence": rnd(y.mean()),
           "brier": rnd(brier_score_loss(y, p)),
           "sensitivity": rnd(tp / max(int(y.sum()), 1)),
           "specificity": rnd(tn / max(int((y == 0).sum()), 1)),
           "auc": rnd(roc_auc_score(y, p)) if two else None, "auc_ci": None,
           "cal_intercept": None, "cal_slope": None}
    if two:
        out["cal_intercept"], out["cal_slope"] = [rnd(v) for v in calibration_terms(y, p)]
        draws = []
        for _ in range(boot):
            idx = rng.integers(0, len(y), len(y))
            if y[idx].min() != y[idx].max():
                draws.append(roc_auc_score(y[idx], p[idx]))
        out["auc_ci"] = [rnd(v) for v in np.percentile(draws, [2.5, 97.5])]
    return out


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    ph = k / n
    denom = 1 + z * z / n
    centre = ph + z * z / (2 * n)
    half = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))
    return [rnd((centre - half) / denom), rnd((centre + half) / denom)]


def calibration_bins(y, p, bins=5):
    frame = pd.DataFrame({"y": y, "p": p})
    try:
        frame["bin"] = pd.qcut(frame["p"], bins, labels=False, duplicates="drop")
    except ValueError:
        return {"predicted": [], "observed": []}
    grouped = frame.groupby("bin").agg(p=("p", "mean"), y=("y", "mean"))
    return {"predicted": [rnd(v) for v in grouped["p"]], "observed": [rnd(v) for v in grouped["y"]]}


def make_bands(y, p, sites):
    positives, negatives = p[y == 1], p[y == 0]
    lower_cut = float(np.quantile(positives, 0.10))
    higher_cut = float(np.quantile(negatives, 0.85))
    if higher_cut <= lower_cut:
        higher_cut = min(lower_cut + 0.15, 0.99)
    label = np.where(p < lower_cut, "lower", np.where(p < higher_cut, "moderate", "higher"))
    stats = {}
    for band in ("lower", "moderate", "higher"):
        mask = label == band
        n, k = int(mask.sum()), int(y[mask].sum())
        per_site = {}
        for site in SITES:
            m = mask & (sites == site)
            per_site[site] = {"n": int(m.sum()), "events": int(y[m].sum()),
                              "rate": rnd(y[m].mean()) if m.sum() else None}
        usable = [v["rate"] for v in per_site.values() if v["n"] >= 10 and v["rate"] is not None]
        stats[band] = {"n": n, "events": k, "rate": rnd(k / n) if n else None, "ci": wilson(k, n),
                       "site_min": min(usable) if usable else None, "site_max": max(usable) if usable else None,
                       "per_site": per_site}
    return {"lower_cut": rnd(lower_cut, 4), "higher_cut": rnd(higher_cut, 4), "stats": stats}


def paper_protocol(frame, rng):
    dev = frame[frame["site"] == "Cleveland"].reset_index(drop=True)
    ext = frame[frame["site"] != "Cleveland"].reset_index(drop=True)
    out = {}
    for name, features in PAPER.items():
        for kind in ("logistic", "forest"):
            oof, count = np.zeros(len(dev)), np.zeros(len(dev))
            cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=10, random_state=SEED)
            for train, test in cv.split(dev[features], dev["target"]):
                model = fit(dev.iloc[train], features, kind)
                oof[test] += model.predict_proba(dev.iloc[test][features])[:, 1]
                count[test] += 1
            final = fit(dev, features, kind)
            external = {}
            for site in SITES[1:]:
                part = ext[ext["site"] == site]
                external[site] = summarize(part["target"].values, final.predict_proba(part[features])[:, 1], rng)
            out[f"{name}_{kind}"] = {
                "features": features,
                "internal": summarize(dev["target"].values, oof / count, rng),
                "external": external,
                "pooled_external": summarize(ext["target"].values, final.predict_proba(ext[features])[:, 1], rng)}
    return out


def leave_one_site_out(frame, features):
    pred = np.zeros(len(frame))
    for site in SITES:
        held = (frame["site"] == site).values
        model = fit(frame[~held], features, "logistic")
        pred[held] = model.predict_proba(frame[held][features])[:, 1]
    return pred


def group_name(column):
    body = column.split("__", 1)[1]
    return body.rsplit("_", 1)[0] if column.startswith("cat__") else body


def deployment(frame, rng):
    y = frame["target"].values
    sites = frame["site"].values
    pipelines, means, tiers = {}, {}, {}
    for tier, features in DEPLOY.items():
        pred = leave_one_site_out(frame, features)
        per_site = {s: summarize(y[sites == s], pred[sites == s], rng) for s in SITES}
        final = fit(frame, features, "logistic")
        pre, clf = final.named_steps["pre"], final.named_steps["clf"]
        names = list(pre.get_feature_names_out())
        pipelines[tier] = final
        means[tier] = pre.transform(frame[features]).mean(axis=0)
        tiers[tier] = {
            "features": features,
            "held_out_site": per_site,
            "held_out_pooled": summarize(y, pred, rng),
            "calibration": {s: calibration_bins(y[sites == s], pred[sites == s]) for s in SITES},
            "bands": make_bands(y, pred, sites),
            "regularisation_C": rnd(float(clf.C_[0]), 4),
            "intercept": rnd(float(clf.intercept_[0]), 4),
            "coefficients": [{"term": n.split("__", 1)[1], "feature": group_name(n), "coef": rnd(float(c))}
                             for n, c in zip(names, clf.coef_[0])]}
    reference = {}
    for feature in ("age", "trestbps", "chol", "thalach", "oldpeak"):
        values = frame[feature].dropna()
        reference[feature] = [rnd(values.quantile(0.01), 2), rnd(values.quantile(0.99), 2)]
    return pipelines, means, tiers, reference


def cohort_summary(frame):
    out = {}
    for site in SITES:
        part = frame[frame["site"] == site]
        out[site] = {"n": int(len(part)), "events": int(part["target"].sum()),
                     "prevalence": rnd(part["target"].mean()), "median_age": rnd(part["age"].median(), 1),
                     "female_pct": rnd((part["sex"] == 0).mean() * 100, 1),
                     "missing_pct": {c: rnd(part[c].isna().mean() * 100, 1) for c in
                                     ["age", "sex", "cp", "trestbps", "chol", "fbs", "restecg", "thalach", "exang",
                                      "oldpeak", "slope", "ca", "thal"]}}
    return out


def train(frame, source, quality, out_dir=ARTIFACT_DIR, run_paper=True):
    rng = np.random.default_rng(SEED)
    pipelines, means, tiers, reference = deployment(frame, rng)
    card = {
        "version": MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_source": source,
        "sklearn_version": sklearn.__version__,
        "cohorts": cohort_summary(frame),
        "zero_values_recoded_as_missing": quality,
        "deployment": tiers,
        "reference_ranges": reference,
        "paper_protocol": paper_protocol(frame, rng) if run_paper else None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"pipelines": pipelines, "means": means}, out_dir / "models.joblib")
    (out_dir / "model_card.json").write_text(json.dumps(card, indent=2))
    return card


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--skip-paper", action="store_true")
    parser.add_argument("--require-real", action="store_true")
    args = parser.parse_args()
    require = args.require_real or os.environ.get("CARDIOLENS_REQUIRE_REAL") == "1"
    frame, source, quality = data.load_cohorts(require_real=require, force_synthetic=args.synthetic)
    card = train(frame, source, quality, run_paper=not args.skip_paper)
    print(f"data source: {source}, records: {len(frame)}")
    for tier, body in card["deployment"].items():
        sites = {s: v["auc"] for s, v in body["held_out_site"].items()}
        print(f"{tier}: held-out AUC by site {sites}, pooled {body['held_out_pooled']['auc']}")
    if card["paper_protocol"]:
        r = card["paper_protocol"]["portable10_logistic"]
        print("paper protocol, portable logistic: internal AUC", r["internal"]["auc"],
              "pooled external AUC", r["pooled_external"]["auc"],
              {s: v["auc"] for s, v in r["external"].items()})


if __name__ == "__main__":
    main()
